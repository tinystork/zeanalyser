"""Tests for the disabled-by-default performance diagnostics instrumentation.

Covers:
- disabled diagnostics are strict no-ops (fast immediate returns)
- enabled diagnostics record counters/events/stages/memory and produce valid JSON
- scientific invariance: a tiny in-process analysis produces identical result rows
  with ``ZEANALYSER_PERF_DIAG=1`` vs unset.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from zeanalyser import analyse_logic, perf_diagnostics, project_state


# --- helpers ---------------------------------------------------------------

def gaussian_field(
    seed: int = 7,
    shape: tuple[int, int] = (96, 96),
    sigma: float = 1.5,
    amplitude: float = 100.0,
    noise: float = 1.0,
    n_stars: int = 9,
    border: int = 16,
):
    """Compact deterministic stellar field with isolated Gaussians."""
    rng = np.random.default_rng(seed)
    img = rng.normal(0.0, noise, shape)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    side = int(np.ceil(np.sqrt(n_stars)))
    step_y = (shape[0] - 2 * border) // max(side - 1, 1)
    step_x = (shape[1] - 2 * border) // max(side - 1, 1)
    for i in range(n_stars):
        cy = border + (i // side) * step_y
        cx = border + (i % side) * step_x
        img = img + amplitude * np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma)
        )
    return img


def _write_fits(path: Path, data: np.ndarray) -> Path:
    fits.PrimaryHDU(data=data.astype(np.float32)).writeto(str(path))
    return path


def _make_fits_dir(root: Path, n: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for idx in range(n):
        _write_fits(root / f"light_{idx}.fit", gaussian_field(seed=idx))
    return root


def _options(root: Path, **overrides):
    options = {
        "include_subfolders": False,
        "analyze_snr": True,
        "detect_trails": False,
        "move_rejected": False,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(root),
    }
    options.update(overrides)
    return options


def _recording_callbacks(logs=None):
    logs = logs if logs is not None else []
    return {
        "is_cancelled": lambda: False,
        "progress": lambda *_a, **_k: None,
        "status": lambda *_a, **_k: None,
        "log": lambda key, **kw: logs.append((key, kw)),
    }


class _InProcessExecutor:
    """ProcessPoolExecutor stand-in that runs the worker synchronously in-process."""

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, fn, path):
        fut = Future()
        fut.set_result(fn(path))
        return fut

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


def _reset_diag(monkeypatch, enabled, out_path):
    """Reset the diagnostics singleton and (re)configure the environment."""
    monkeypatch.setattr(perf_diagnostics, "_DIAG", None)
    if enabled:
        monkeypatch.setenv("ZEANALYSER_PERF_DIAG", "1")
        monkeypatch.setenv("ZEANALYSER_PERF_DIAG_OUT", str(out_path))
    else:
        monkeypatch.delenv("ZEANALYSER_PERF_DIAG", raising=False)
        monkeypatch.delenv("ZEANALYSER_PERF_DIAG_OUT", raising=False)


# --- disabled no-ops -------------------------------------------------------

def test_disabled_diagnostics_are_no_ops():
    diag = perf_diagnostics.PerfDiagnostics(enabled=False)
    assert diag.enabled is False
    assert diag.start_run(output_log="x") is None
    assert diag.stage_start("a") is None
    assert diag.stage_end("a", files=1) is None
    assert diag.counter("c") is None
    assert diag.event("e", n=1) is None
    assert diag.completed_image() is None
    assert diag.sample_memory("m") is None
    assert diag.finish_run() is None
    # no internal state was accumulated
    assert diag._counters == {}
    assert diag._events == []
    assert diag._stages == {}
    assert diag._memory_samples == []
    assert diag._image_completion == []


def test_get_diagnostics_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ZEANALYSER_PERF_DIAG", raising=False)
    monkeypatch.setattr(perf_diagnostics, "_DIAG", None)
    diag = perf_diagnostics.get_diagnostics()
    assert diag.enabled is False
    assert diag.finish_run() is None


# --- enabled recording -----------------------------------------------------

def test_enabled_diagnostics_record_and_flush_valid_json(tmp_path):
    out = tmp_path / "diag.json"
    diag = perf_diagnostics.PerfDiagnostics(enabled=True, output_path=str(out))

    diag.start_run(output_log=str(tmp_path / "log.log"), run_id="r1")
    diag.stage_start("fits_enumeration")
    diag.stage_end("fits_enumeration", files=3)
    diag.stage_start("submission")
    diag.stage_end("submission", total_jobs=3)
    diag.counter("progress_calls", 2)
    diag.counter("progress_calls", 3)
    diag.event("custom_event", n=3)
    diag.completed_image()
    diag.completed_image()
    diag.sample_memory("snr_0")
    diag.finish_run()

    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["meta"]["run_id"] == "r1"
    assert report["wall_seconds"] >= 0.0
    assert set(report["stages"]) == {"fits_enumeration", "submission"}
    assert report["stages"]["fits_enumeration"]["duration_seconds"] >= 0.0
    assert report["stages"]["fits_enumeration"]["fields"] == {"files": 3}
    assert report["counters"] == {"progress_calls": 5}
    assert len(report["image_completion"]) == 2
    assert [m["label"] for m in report["memory_samples"]] == ["start", "snr_0"]
    assert all(m["rss_kb"] >= 0 for m in report["memory_samples"])
    assert len(report["events"]) == 1
    assert report["events"][0]["name"] == "custom_event"
    assert report["events"][0]["n"] == 3

    # finish_run is idempotent
    diag.finish_run()
    assert report == json.loads(out.read_text(encoding="utf-8"))


# --- scientific invariance -------------------------------------------------

def test_scientific_invariance_diag_on_vs_off(tmp_path, monkeypatch):
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _InProcessExecutor,
    )

    dir_data = _make_fits_dir(tmp_path / "data", 2)
    diag_out = tmp_path / "za_perf_diag.json"
    log_path = str(dir_data / project_state.DEFAULT_LOG_FILENAME)

    # disabled run
    _reset_diag(monkeypatch, enabled=False, out_path=diag_out)
    rows_off = analyse_logic.perform_analysis(
        str(dir_data),
        log_path,
        _options(dir_data),
        _recording_callbacks(),
    )

    # enabled run (perform_analysis itself invalidates the previous run's
    # completion marker, so the same directory is re-analysed identically)
    _reset_diag(monkeypatch, enabled=True, out_path=diag_out)
    rows_on = analyse_logic.perform_analysis(
        str(dir_data),
        log_path,
        _options(dir_data),
        _recording_callbacks(),
    )

    assert len(rows_off) == len(rows_on) == 2
    # as_completed yields already-done futures in a non-deterministic set order
    # (pre-existing), so compare per-file values order-insensitively without
    # weakening the scientific assertion.
    _key = lambda d: d.get('rel_path') or d.get('file') or ''
    off = sorted((analyse_logic.sanitize_for_json(r) for r in rows_off), key=_key)
    on = sorted((analyse_logic.sanitize_for_json(r) for r in rows_on), key=_key)
    assert off == on

    # the diagnostics report was written for the enabled run
    assert diag_out.exists()
    report = json.loads(diag_out.read_text(encoding="utf-8"))
    assert report["counters"].get("progress_calls", 0) > 0
    assert report["counters"].get("log_calls", 0) > 0
    assert report["counters"].get("status_calls", 0) > 0
    assert "fits_enumeration" in report["stages"]
    assert "executor_startup" in report["stages"]
    assert "submission" in report["stages"]
