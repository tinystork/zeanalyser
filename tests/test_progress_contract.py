"""Tests for the global analysis progress-bar contract (UX-only).

The patch maps the phases actually enabled onto a contiguous [0, 100] range:

- SNR-only  : discovery 0-2, SNR 2-90, SNR selection 90-95, finalize 95-100
- SNR+trails: discovery 0-2, SNR 2-55, selection 55-60, trail detection 60-90,
              trail marking 90-95, finalize 95-100

These tests use the same in-process ``ProcessPoolExecutor`` stub as
``test_perf_diagnostics.py``: ``submit`` runs the worker synchronously and
immediately sets the ``Future`` result.
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import numpy as np
from astropy.io import fits

from zeanalyser import analyse_logic, project_state


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


def _run(tmp_path, monkeypatch, *, files=2, progress, is_cancelled, **opt_overrides):
    """Run SNR-only perform_analysis in-process and return its result rows."""
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _InProcessExecutor,
    )
    data = _make_fits_dir(tmp_path / "data", files)
    callbacks = {
        "is_cancelled": is_cancelled,
        "progress": progress,
        "status": lambda *_a, **_k: None,
        "log": lambda *_a, **_k: None,
    }
    rows = analyse_logic.perform_analysis(
        str(data),
        str(data / project_state.DEFAULT_LOG_FILENAME),
        _options(data, **opt_overrides),
        callbacks,
    )
    return rows


def _assert_contiguous_and_covering(plan):
    ordered = ['discovery', 'snr', 'snr_selection']
    if 'trail_detection' in plan:
        ordered += ['trail_detection', 'trail_marking']
    ordered += ['finalize']

    assert plan['discovery'][0] == 0.0
    assert plan['finalize'][1] == 100.0
    for prev, cur in zip(ordered, ordered[1:]):
        assert plan[prev][1] == plan[cur][0], (
            f"phase boundary mismatch between {prev} and {cur}"
        )
    # monotonic within every phase
    for phase in ordered:
        start, end = plan[phase]
        assert start <= end


# --- plan building ---------------------------------------------------------

def test_build_progress_plan_snr_only():
    plan = analyse_logic._build_progress_plan(False)
    assert plan['snr'] == (2.0, 90.0)
    assert 'trail_detection' not in plan
    assert 'trail_marking' not in plan
    assert plan['snr_selection'] == (90.0, 95.0)
    assert plan['finalize'] == (95.0, 100.0)
    _assert_contiguous_and_covering(plan)


def test_build_progress_plan_trails():
    plan = analyse_logic._build_progress_plan(True)
    assert plan['snr'] == (2.0, 55.0)
    assert 'trail_detection' in plan
    assert 'trail_marking' in plan
    assert plan['snr_selection'] == (55.0, 60.0)
    assert plan['trail_detection'] == (60.0, 90.0)
    assert plan['trail_marking'] == (90.0, 95.0)
    assert plan['finalize'] == (95.0, 100.0)
    _assert_contiguous_and_covering(plan)


# --- runtime contract ------------------------------------------------------

def test_snr_only_run_progress_monotonic_and_reaches_100(tmp_path, monkeypatch):
    captured = []

    def progress(value):
        captured.append(float(value))

    rows = _run(
        tmp_path,
        monkeypatch,
        files=2,
        progress=progress,
        is_cancelled=lambda: False,
    )

    assert len(rows) == 2
    assert captured, "no progress callbacks captured"
    assert all(0.0 <= v <= 100.0 for v in captured)
    assert all(
        captured[i] <= captured[i + 1] for i in range(len(captured) - 1)
    ), "progress values must be non-decreasing"
    assert captured[-1] == 100.0


def test_snr_only_run_reaches_high_range_during_snr(tmp_path, monkeypatch):
    captured = []

    def progress(value):
        captured.append(float(value))

    _run(
        tmp_path,
        monkeypatch,
        files=2,
        progress=progress,
        is_cancelled=lambda: False,
    )

    assert max(captured) >= 88.0, (
        "SNR phase should reach ~90 when trails are disabled (no fake 50 cap)"
    )


def test_cancelled_run_never_reaches_100(tmp_path, monkeypatch):
    captured = []
    state = {"cancelled": False, "calls": 0}

    def progress(value):
        captured.append(float(value))
        state["calls"] += 1
        if state["calls"] >= 2:
            state["cancelled"] = True

    def is_cancelled():
        return state["cancelled"]

    rows = _run(
        tmp_path,
        monkeypatch,
        files=2,
        progress=progress,
        is_cancelled=is_cancelled,
    )

    assert rows == []
    assert 100.0 not in captured


def test_scientific_rows_unchanged_by_progress_patch(tmp_path, monkeypatch):
    rows = _run(
        tmp_path,
        monkeypatch,
        files=2,
        progress=lambda value: None,
        is_cancelled=lambda: False,
    )

    assert len(rows) == 2
    for r in rows:
        assert r.get('status') == 'ok'
        assert np.isfinite(r.get('snr', np.nan))
        assert np.isfinite(r.get('fwhm', np.nan))
        assert np.isfinite(r.get('ecc', np.nan))
        assert r.get('starcount') is not None
        assert np.isfinite(r.get('starcount', np.nan))
