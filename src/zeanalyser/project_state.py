"""Shared ZeAnalyser project-state and completion-marker contracts.

The completion marker controls the "already processed" contract. Persisted
visualization data controls whether an existing project can be reopened. Those
contracts are deliberately related but independent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable, Iterator

NEW_MARKER_FILENAME = "ZeAnalyser.marker.json"
LEGACY_MARKER_FILENAME = ".astro_analyzer_run_complete"
MARKER_SCHEMA_VERSION = 1
PRODUCT_NAME = "ZeAnalyser"
DEFAULT_LOG_FILENAME = "analyse_resultats.log"

VISUALIZATION_BEGIN = "--- BEGIN VISUALIZATION DATA ---"
VISUALIZATION_END = "--- END VISUALIZATION DATA ---"


@dataclass(frozen=True)
class MarkerInfo:
    path: Path
    legacy: bool
    metadata: dict | None = None


def _safe_relative_path(project_dir: Path, value: object) -> Path | None:
    """Resolve a relative path without allowing it to escape *project_dir*."""

    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute():
        return None
    try:
        root = project_dir.resolve()
        candidate = (root / relative).resolve()
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            return None
    except (OSError, ValueError):
        return None
    return candidate


def _valid_completed_at(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def read_marker(marker_path: str | os.PathLike[str]) -> MarkerInfo | None:
    """Read and validate a recognized marker.

    Legacy markers are recognized by filename and existence only. A malformed
    new marker is not accepted as a completion sentinel.
    """

    path = Path(marker_path)
    if path.name == LEGACY_MARKER_FILENAME:
        return MarkerInfo(path=path, legacy=True) if path.is_file() else None
    if path.name != NEW_MARKER_FILENAME or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as stream:
            metadata = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("schema_version") != MARKER_SCHEMA_VERSION:
        return None
    if metadata.get("product") != PRODUCT_NAME:
        return None
    if not _valid_completed_at(metadata.get("completed_at_utc")):
        return None
    if _safe_relative_path(path.parent, metadata.get("log_file")) is None:
        return None
    return MarkerInfo(path=path, legacy=False, metadata=metadata)


def marker_paths(directory: str | os.PathLike[str]) -> tuple[Path, ...]:
    """Return existing files with recognized ZeAnalyser marker filenames.

    This physical-file view is intended for marker management, including
    cleanup of malformed new markers. It never includes unrelated files.
    """

    root = Path(directory)
    found = []
    for filename in (NEW_MARKER_FILENAME, LEGACY_MARKER_FILENAME):
        path = root / filename
        if path.is_file():
            found.append(path)
    return tuple(found)


def find_marker(directory: str | os.PathLike[str]) -> MarkerInfo | None:
    """Return the preferred valid marker, new format first, then legacy."""

    root = Path(directory)
    marker = read_marker(root / NEW_MARKER_FILENAME)
    if marker is not None:
        return marker
    return read_marker(root / LEGACY_MARKER_FILENAME)


def has_analysis_marker(directory: str | os.PathLike[str]) -> bool:
    return find_marker(directory) is not None


def marker_metadata_invalid(directory: str | os.PathLike[str]) -> bool:
    """Return True when a new marker exists but does not validate."""

    path = Path(directory) / NEW_MARKER_FILENAME
    return path.is_file() and read_marker(path) is None


def iter_marked_directories(
    root_dir: str | os.PathLike[str],
    *,
    excluded_dirs: Iterable[str | os.PathLike[str]] = (),
    include_invalid_new: bool = False,
) -> Iterator[Path]:
    """Yield marked directories recursively while pruning excluded trees."""

    root = Path(root_dir).resolve()
    excluded = {Path(path).resolve() for path in excluded_dirs}
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        current = Path(dirpath).resolve()
        dirnames[:] = [name for name in dirnames if (current / name).resolve() not in excluded]
        if has_analysis_marker(current) or (include_invalid_new and marker_paths(current)):
            yield current


def remove_markers(directory: str | os.PathLike[str]) -> tuple[Path, ...]:
    """Remove both recognized marker generations and no other files."""

    removed = []
    for path in marker_paths(directory):
        path.unlink()
        removed.append(path)
    return tuple(removed)


def resolve_marker_log_path(directory: str | os.PathLike[str]) -> Path | None:
    """Resolve a safe log reference from a valid new marker.

    Legacy markers have no metadata and therefore return ``None`` so callers
    can use conventional ``analyse_resultats.log`` discovery.
    """

    marker = find_marker(directory)
    if marker is None or marker.legacy or marker.metadata is None:
        return None
    return _safe_relative_path(Path(directory), marker.metadata.get("log_file"))


def write_marker_atomic(
    directory: str | os.PathLike[str],
    log_file: str | os.PathLike[str] = DEFAULT_LOG_FILENAME,
    *,
    completed_at_utc: datetime | None = None,
    product_version: str | None = None,
) -> Path:
    """Atomically write the canonical completion marker.

    ``log_file`` must be relative and confined to ``directory``. The final
    marker appears only after complete JSON has been flushed and fsynced.
    """

    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    log_value = os.fspath(log_file)
    if _safe_relative_path(root, log_value) is None:
        raise ValueError("marker log_file must be a safe relative project path")

    when = completed_at_utc or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    payload = {
        "schema_version": MARKER_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "completed_at_utc": when.isoformat().replace("+00:00", "Z"),
        "log_file": log_value.replace(os.sep, "/"),
    }
    if product_version:
        payload["product_version"] = str(product_version)

    final_path = root / NEW_MARKER_FILENAME
    fd, temp_name = tempfile.mkstemp(prefix=f".{NEW_MARKER_FILENAME}.", suffix=".tmp", dir=root)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, final_path)
        try:
            dir_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise
    return final_path


def load_latest_valid_visualization_block(
    log_path: str | os.PathLike[str],
) -> list | None:
    """Stream a log and return its last complete, valid visualization list.

    Only the active JSON block is spooled (to disk beyond 1 MiB); the entire
    log is never materialized. Invalid or incomplete trailing blocks are
    ignored, preserving the latest earlier valid dataset.
    """

    latest = None
    block = None
    try:
        with Path(log_path).open("r", encoding="utf-8") as stream:
            for line in stream:
                marker = line.strip()
                if marker == VISUALIZATION_BEGIN:
                    if block is not None:
                        block.close()
                    block = tempfile.SpooledTemporaryFile(
                        mode="w+", max_size=1024 * 1024, encoding="utf-8"
                    )
                    continue
                if marker == VISUALIZATION_END:
                    if block is None:
                        continue
                    try:
                        block.seek(0)
                        candidate = json.load(block)
                        if isinstance(candidate, list):
                            latest = candidate
                    except (json.JSONDecodeError, UnicodeError, ValueError):
                        pass
                    finally:
                        block.close()
                        block = None
                    continue
                if block is not None:
                    block.write(line)
    finally:
        if block is not None:
            block.close()
    return latest
