"""Correctness tests for FWHM/ECC measurement.

Covers the Photutils 3.0.0 centroid-column incompatibility (Defect A) and the
new structured outcome / central aggregation behaviour (E1-E5).
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table

from zeanalyser import analyse_logic, project_state
from zeanalyser import ecc_module


# --- remote/test helpers -----------------------------------------------------

def gaussian_field(
    seed: int = 7,
    shape: tuple[int, int] = (160, 160),
    sigma: float = 1.5,
    amplitude: float = 100.0,
    noise: float = 1.0,
    n_stars: int = 9,
    border: int = 20,
):
    """Compact deterministic 2-D stellar field with isolated Gaussians."""
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


def _recording_callbacks(logs):
    return {
        "is_cancelled": lambda: False,
        "progress": lambda *_a, **_k: None,
        "status": lambda *_a, **_k: None,
        "log": lambda key, **kw: logs.append((key, kw)),
    }


class _RaisingExecutor:
    """ProcessPoolExecutor stand-in forcing the sequential fallback."""

    def __init__(self, **_kwargs):
        raise RuntimeError("pool unavailable for test")


class _ImmediateMetricFailureExecutor:
    """Pool stand-in returning a measurement-failure worker result per file."""

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.shutdown(wait=True)
        return False

    def submit(self, _function, path):
        future = Future()
        future.set_result(
            {
                "path": path,
                "snr": 20.0,
                "sky_bg": 1.0,
                "sky_noise": 1.0,
                "signal_pixels": 10,
                "starcount": 5,
                "exposure": 10.0,
                "filter": "LP",
                "temperature": 0.0,
                "eqmode": 2,
                "sitelong": None,
                "sitelat": None,
                "telescope": "Seestar",
                "date_obs": "2026-09-14T00:00:00",
                "error": None,
                "fwhm": np.nan,
                "ecc": np.nan,
                "n_star_ecc": 0,
                "fwhm_ecc_outcome": "measurement_failure",
                "fwhm_ecc_error": "KeyError: 'xcentroid'",
                "ra": None,
                "dec": None,
            }
        )
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


# --- E1 / E3 / E4 / E5: measurement level ------------------------------------

def test_e1_synthetic_field_measures_finite_metrics():
    outcome = ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())
    assert outcome["outcome"] == "ok"
    assert outcome["n"] > 0
    assert np.isfinite(outcome["fwhm"]) and outcome["fwhm"] > 0
    assert np.isfinite(outcome["ecc"])
    assert 0.0 <= outcome["ecc"] <= 1.0

    # backward-compatible 3-tuple is preserved
    fwhm, ecc, n = ecc_module.calculate_fwhm_ecc(gaussian_field())
    assert (fwhm, ecc, n) == (outcome["fwhm"], outcome["ecc"], outcome["n"])


def test_e3_flat_image_is_no_detections_not_failure():
    flat = np.full((120, 120), 5.0)
    outcome = ecc_module.calculate_fwhm_ecc_outcome(flat)
    assert outcome["outcome"] == "no_detections"
    assert outcome["outcome"] != "measurement_failure"
    assert np.isnan(outcome["fwhm"]) and np.isnan(outcome["ecc"])
    assert outcome["n"] == 0
    fwhm, ecc, n = ecc_module.calculate_fwhm_ecc(flat)
    assert np.isnan(fwhm) and np.isnan(ecc) and n == 0


def test_e4_injected_exception_is_measurement_failure(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise ValueError("injected metric failure")

    monkeypatch.setattr(ecc_module, "_measure_fwhm_ecc", _boom)
    outcome = ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())
    assert outcome["outcome"] == "measurement_failure"
    assert "injected metric failure" in (outcome["reason"] or "")
    assert outcome["n"] == 0
    # legacy tuple must not raise
    fwhm, ecc, n = ecc_module.calculate_fwhm_ecc(gaussian_field())
    assert np.isnan(fwhm) and np.isnan(ecc) and n == 0


def test_unsupported_centroid_columns_is_measurement_failure(monkeypatch):
    """No legacy and no modern centroid column => internal failure, not no_detections."""
    tbl = Table({"id": [1, 2], "flux": [10.0, 20.0]})

    def _fake_detect(*_args, **_kwargs):
        return 0.0, 1.0, tbl

    monkeypatch.setattr(ecc_module, "_detect_stars", _fake_detect)
    outcome = ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())
    assert outcome["outcome"] == "measurement_failure"
    assert "unsupported centroid columns" in (outcome["reason"] or "")
    assert outcome["outcome"] != "no_detections"


def test_e5_legacy_and_modern_centroid_columns_agree(monkeypatch):
    """Both Photutils column naming forms must yield identical finite values."""
    field = gaussian_field()
    bg, noise, tbl = ecc_module._detect_stars(field, 3.5, 5.0)
    assert tbl is not None and len(tbl) > 0
    assert "x_centroid" in tbl.colnames  # current Photutils naming

    modern = tbl.copy()
    legacy = tbl.copy()
    legacy.rename_column("x_centroid", "xcentroid")
    legacy.rename_column("y_centroid", "ycentroid")

    results = {}
    for name, table in (("modern", modern), ("legacy", legacy)):
        monkeypatch.setattr(
            ecc_module, "_detect_stars", lambda *_a, _t=table, **_k: (bg, noise, _t)
        )
        results[name] = ecc_module.calculate_fwhm_ecc_outcome(field)

    assert results["modern"]["outcome"] == "ok"
    assert results["legacy"]["outcome"] == "ok"
    assert results["modern"]["n"] == results["legacy"]["n"]
    assert results["modern"]["fwhm"] == pytest.approx(results["legacy"]["fwhm"])
    assert results["modern"]["ecc"] == pytest.approx(results["legacy"]["ecc"])
    assert np.isfinite(results["legacy"]["fwhm"])

    # measurement math is the documented one: FWHM = 2.3548 * sigma for a
    # circular Gaussian with sigma = 1.5 px
    assert results["modern"]["fwhm"] == pytest.approx(2.3548 * 1.5, rel=0.03)


# --- E2 / E4: real image-worker path ----------------------------------------

def test_e2_image_worker_populates_all_metrics(tmp_path):
    path = _write_fits(tmp_path / "light.fit", gaussian_field())

    result = analyse_logic._snr_worker(str(path))

    assert result["error"] is None
    assert np.isfinite(result["snr"])
    assert result["starcount"] is not None and result["starcount"] > 0
    assert np.isfinite(result["fwhm"]) and result["fwhm"] > 0
    assert np.isfinite(result["ecc"])
    assert result["n_star_ecc"] > 0
    assert result["fwhm_ecc_outcome"] == "ok"
    assert result["fwhm_ecc_error"] is None


def test_e4_worker_metric_failure_keeps_valid_snr(tmp_path, monkeypatch):
    path = _write_fits(tmp_path / "light.fit", gaussian_field())

    def _boom(*_args, **_kwargs):
        raise RuntimeError("injected worker metric failure")

    monkeypatch.setattr(ecc_module, "calculate_fwhm_ecc_outcome", _boom)
    result = analyse_logic._snr_worker(str(path))

    # a measurement failure must never be reported as a file-level error
    assert result["error"] is None
    assert np.isfinite(result["snr"])
    assert np.isnan(result["fwhm"]) and np.isnan(result["ecc"])
    assert result["n_star_ecc"] == 0
    assert result["fwhm_ecc_outcome"] == "measurement_failure"
    assert "injected worker metric failure" in result["fwhm_ecc_error"]


# --- aggregation -------------------------------------------------------------

def test_aggregation_pool_branch_counts_bounded_examples(tmp_path, monkeypatch):
    for idx in range(4):
        (tmp_path / f"light_{idx}.fit").touch()
    logs = []
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _ImmediateMetricFailureExecutor,
    )
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _recording_callbacks(logs),
    )

    summaries = [entry for entry in logs if entry[0] == "logic_fwhm_ecc_measurement_failures"]
    assert len(summaries) == 1, "exactly one aggregated summary line expected"
    key, kwargs = summaries[0]
    assert kwargs["count"] == 4
    assert kwargs["file"]  # first bounded example
    assert "xcentroid" in kwargs["reason"]
    # no per-image tracebacks / file errors
    assert not [entry for entry in logs if entry[0] == "logic_file_error"]
    assert all(row["status"] == "ok" for row in rows)


def test_aggregation_sequential_fallback_matches_pool(tmp_path, monkeypatch):
    paths = []
    for idx in range(3):
        paths.append(_write_fits(tmp_path / f"light_{idx}.fit", gaussian_field(seed=idx)))

    def _boom(*_args, **_kwargs):
        raise ValueError("injected metric failure")

    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ProcessPoolExecutor", _RaisingExecutor
    )
    monkeypatch.setattr(ecc_module, "calculate_fwhm_ecc_outcome", _boom)

    logs = []
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _recording_callbacks(logs),
    )

    assert [entry[0] for entry in logs].count("logic_snr_pool_fallback") == 1
    summaries = [entry for entry in logs if entry[0] == "logic_fwhm_ecc_measurement_failures"]
    assert len(summaries) == 1
    kwargs = summaries[0][1]
    assert kwargs["count"] == len(paths)
    assert "injected metric failure" in kwargs["reason"]
    # measurement failure did not turn the files into errors
    assert all(row["status"] == "ok" for row in rows)
    assert np.isfinite(rows[0]["snr"])
