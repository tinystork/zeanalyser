"""Backend for the Organizer tab (Seestar FITS sorter).

This module scans FITS files, classifies them based on Seestar headers, and
builds/apply move/copy plans without touching the analysis pipeline.
"""

from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Tuple

FIT_EXTS = (".fit", ".fits")


def _normalize_callbacks(callbacks):
    callbacks = callbacks or {}
    status_cb = callbacks.get("status") if isinstance(callbacks, dict) else None
    progress_cb = callbacks.get("progress") if isinstance(callbacks, dict) else None
    log_cb = callbacks.get("log") if isinstance(callbacks, dict) else None
    cancel_cb = callbacks.get("is_cancelled") if isinstance(callbacks, dict) else None

    def is_cancelled():
        try:
            return bool(cancel_cb()) if cancel_cb else False
        except Exception:
            return False

    return status_cb, progress_cb, log_cb, is_cancelled


def iter_fits_files(input_dir: str, include_subfolders: bool, skip_dirs_abs=None) -> list[str]:
    """Return FIT/FITS files from input_dir, optionally recursing subfolders."""
    if not input_dir:
        return []
    input_dir = os.path.abspath(input_dir)
    skip_dirs_abs = {os.path.abspath(p) for p in (skip_dirs_abs or [])}

    files: list[str] = []

    def _should_skip_dir(path: str) -> bool:
        return any(os.path.commonpath([path, s]) == s for s in skip_dirs_abs) if skip_dirs_abs else False

    if not include_subfolders:
        try:
            for name in os.listdir(input_dir):
                path = os.path.join(input_dir, name)
                if os.path.isfile(path) and name.lower().endswith(FIT_EXTS) and not _should_skip_dir(path):
                    files.append(os.path.abspath(path))
        except Exception:
            return files
        return files

    for root, dirs, filenames in os.walk(input_dir):
        root_abs = os.path.abspath(root)
        if _should_skip_dir(root_abs):
            dirs[:] = []
            continue
        try:
            dirs[:] = [d for d in dirs if not _should_skip_dir(os.path.join(root_abs, d))]
        except Exception:
            pass
        for name in filenames:
            if name.lower().endswith(FIT_EXTS):
                files.append(os.path.abspath(os.path.join(root_abs, name)))

    return files


def read_seestar_tags(path: str) -> dict:
    """Read EQMODE and FILTER from HDU0 header."""
    result = {"eqmode_raw": None, "filter_raw": None, "error": None}
    try:
        from astropy.io import fits

        header = fits.getheader(path, 0)
        result["eqmode_raw"] = header.get("EQMODE")
        result["filter_raw"] = header.get("FILTER")
    except Exception as e:  # pragma: no cover - defensive
        result["error"] = str(e)
    return result


def classify_mount(eqmode_raw) -> str:
    if eqmode_raw is None:
        return "NO_EQMODE"
    try:
        v = int(eqmode_raw)
        if v == 1:
            return "EQ"
        if v == 0:
            return "ALTZ"
    except Exception:
        pass
    return "NO_EQMODE"


def classify_filter(filter_raw) -> str:
    if filter_raw is None:
        return "UNKNOWN_FILTER"
    val = str(filter_raw).strip().upper()
    if not val:
        return "UNKNOWN_FILTER"
    if "IRCUT" in val:
        return "IRCUT"
    if "LP" in val:
        return "LP"
    return "UNKNOWN_FILTER"


def _empty_filter_bucket() -> dict:
    return {"IRCUT": 0, "LP": 0, "UNKNOWN_FILTER": 0}


def _empty_summary() -> dict:
    return {
        "input_count": 0,
        "processed": 0,
        "planned": 0,
        "errors": 0,
        "error_files": [],
        "skipped_existing": 0,
        "cancelled": False,
        "by_mount": {
            "EQ": _empty_filter_bucket(),
            "ALTZ": _empty_filter_bucket(),
            "NO_EQMODE": _empty_filter_bucket(),
        },
    }


def _resolve_collision_path(dst_abs: str) -> str:
    if not os.path.exists(dst_abs):
        return dst_abs
    base, ext = os.path.splitext(dst_abs)
    idx = 1
    while True:
        candidate = f"{base}__{idx:02d}{ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def build_plan(
    files: Iterable[str],
    input_dir: str,
    dest_root: str,
    preserve_rel: bool = False,
    callbacks=None,
    skip_already_organized: bool = True,
) -> Tuple[list[dict], dict]:
    """Build a move/copy plan for the provided FITS files."""
    status_cb, progress_cb, log_cb, is_cancelled = _normalize_callbacks(callbacks)
    files_list = [os.path.abspath(f) for f in files]
    total = len(files_list)

    input_dir_abs = os.path.abspath(input_dir) if input_dir else ""
    dest_root_abs = os.path.abspath(dest_root) if dest_root else ""

    summary = _empty_summary()
    summary["input_count"] = total
    entries: list[dict] = []

    if status_cb:
        status_cb("organizer_scan_start")

    if not files_list:
        if status_cb:
            status_cb("organizer_scan_done")
        return entries, summary

    workers = min(8, os.cpu_count() or 4)
    processed = 0

    def _should_skip(src_path: str) -> bool:
        if not (skip_already_organized and dest_root_abs):
            return False
        try:
            return os.path.commonpath([dest_root_abs, src_path]) == dest_root_abs
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        tag_results = pool.map(read_seestar_tags, files_list)
        for idx, (src_abs, tags) in enumerate(zip(files_list, tag_results)):
            if is_cancelled():
                summary["cancelled"] = True
                break
            processed += 1

            if _should_skip(src_abs):
                summary["skipped_existing"] += 1
                continue

            err = tags.get("error")
            if err:
                summary["errors"] += 1
                summary["error_files"].append({"file": src_abs, "error": err})
                if log_cb:
                    log_cb(f"[organizer] header error: {src_abs}: {err}")
                continue

            mount_bucket = classify_mount(tags.get("eqmode_raw"))
            filter_bucket = classify_filter(tags.get("filter_raw"))
            rel_dir = ""
            try:
                rel_dir = os.path.relpath(os.path.dirname(src_abs), input_dir_abs)
                if rel_dir == "." or rel_dir.startswith(".."):
                    rel_dir = ""
            except Exception:
                rel_dir = ""

            dest_dir = os.path.join(dest_root_abs, mount_bucket, filter_bucket)
            if preserve_rel and rel_dir:
                dest_dir = os.path.join(dest_dir, rel_dir)
            dst_abs = os.path.join(dest_dir, os.path.basename(src_abs))
            dst_abs = _resolve_collision_path(dst_abs)

            entry = {
                "src_abs": src_abs,
                "dst_abs": dst_abs,
                "mount_bucket": mount_bucket,
                "filter_bucket": filter_bucket,
                "status": "ok",
            }
            entries.append(entry)
            summary["planned"] += 1
            try:
                summary["by_mount"][mount_bucket][filter_bucket] += 1
            except Exception:
                pass

            if progress_cb and total:
                try:
                    progress_cb((idx + 1) * 100.0 / total)
                except Exception:
                    pass

    summary["processed"] = processed

    if status_cb:
        status_cb("organizer_scan_done")

    return entries, summary


def apply_plan(entries: list[dict], move_files: bool, dry_run: bool, callbacks=None) -> dict:
    """Apply the move/copy plan to disk."""
    status_cb, progress_cb, log_cb, is_cancelled = _normalize_callbacks(callbacks)
    summary = {
        "planned": len([e for e in entries if e.get("status") == "ok"]),
        "moved": 0,
        "copied": 0,
        "skipped": 0,
        "errors": 0,
        "cancelled": False,
        "dry_run": bool(dry_run),
    }

    if status_cb:
        status_cb("organizer_apply_start")

    total = len(entries)
    for idx, entry in enumerate(entries):
        if is_cancelled():
            summary["cancelled"] = True
            break

        if entry.get("status") != "ok":
            summary["skipped"] += 1
            continue

        src_abs = entry.get("src_abs")
        dst_abs = entry.get("dst_abs")
        if not src_abs or not dst_abs:
            summary["errors"] += 1
            continue

        final_dst = _resolve_collision_path(dst_abs)
        entry["resolved_dst"] = final_dst

        if dry_run:
            summary["skipped"] += 1
            continue

        try:
            os.makedirs(os.path.dirname(final_dst), exist_ok=True)
            if move_files:
                shutil.move(src_abs, final_dst)
                summary["moved"] += 1
                entry["status"] = "moved"
            else:
                shutil.copy2(src_abs, final_dst)
                summary["copied"] += 1
                entry["status"] = "copied"
            entry["applied_dst"] = final_dst
            if log_cb:
                action = "moved" if move_files else "copied"
                log_cb(f"[organizer] {action}: {src_abs} -> {final_dst}")
        except Exception as e:
            summary["errors"] += 1
            entry["status"] = "error"
            entry["error"] = str(e)
            if log_cb:
                log_cb(f"[organizer] error moving {src_abs}: {e}")

        if progress_cb and total:
            try:
                progress_cb((idx + 1) * 100.0 / total)
            except Exception:
                pass

    if status_cb:
        status_cb("organizer_apply_done")

    return summary
