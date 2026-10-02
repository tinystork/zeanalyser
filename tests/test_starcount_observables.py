"""Starcount observability tests (BASE-02).

Covers the structured starcount outcome contract, pool/fallback parity,
aggregated measurement-failure logging, failure≠0 rejection behaviour,
persistence/reopen fidelity, and the wrapper contract.
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from zeanalyser import analyse_logic, analysis_schema, project_state
from zeanalyser import starcount_module


def _qt_available() -> bool:
    try:
        import zeanalyser.analyse_gui_qt as gui_mod
        return gui_mod.QApplication is not object
    except Exception:
        return False


# --- helpers ----------------------------------------------------------------

def gaussian_field(
    seed: int = 7,
    shape: tuple[int, int] = (160, 160),
    sigma: float = 1.5,
    amplitude: float = 100.0,
    noise: float = 1.0,
    n_stars: int = 9,
    border: int = 20,
):
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


def _starcount_failure_result(path: str) -> dict:
    return {
        "path": path,
        "snr": 20.0,
        "sky_bg": 1.0,
        "sky_noise": 1.0,
        "signal_pixels": 10,
        "starcount": None,
        "starcount_outcome": "measurement_failure",
        "starcount_error": "unable to establish valid background/noise statistics",
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
        "fwhm_ecc_outcome": "no_detections",
        "fwhm_ecc_error": None,
        "ra": None,
        "dec": None,
    }


class _StarcountFailureExecutor:
    """Pool stand-in returning a starcount measurement-failure result per file."""

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.shutdown(wait=True)
        return False

    def submit(self, _function, path):
        future = Future()
        future.set_result(_starcount_failure_result(path))
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


class _CountThenRaiseExecutor:
    """Pool stand-in: every file yields a starcount failure, then the pool dies."""

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        raise RuntimeError("pool died after draining all results")

    def submit(self, _function, path):
        future = Future()
        future.set_result(_starcount_failure_result(path))
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


# --- outcome contract -------------------------------------------------------

def test_outcome_ok_counts_stars():
    outcome = starcount_module.calculate_starcount_outcome(gaussian_field())
    assert outcome["outcome"] == "ok"
    assert outcome["count"] > 0
    assert outcome["reason"] is None


def test_outcome_genuine_no_detections_is_zero():
    rng = np.random.default_rng(3)
    noise = rng.normal(0.0, 1.0, (160, 160))
    outcome = starcount_module.calculate_starcount_outcome(noise)
    assert outcome["outcome"] == "no_detections"
    assert outcome["count"] == 0


def test_outcome_flat_image_is_measurement_failure_not_zero():
    flat = np.full((120, 120), 5.0)
    outcome = starcount_module.calculate_starcount_outcome(flat)
    assert outcome["outcome"] == "measurement_failure"
    assert outcome["count"] is None
    assert outcome["reason"]


def test_outcome_invalid_input_is_measurement_failure():
    # all-NaN input
    nan_arr = np.full((120, 120), np.nan)
    assert starcount_module.calculate_starcount_outcome(nan_arr)["outcome"] == "measurement_failure"
    # non-2-D input
    assert starcount_module.calculate_starcount_outcome(np.zeros(10))["outcome"] == "measurement_failure"
    # empty input
    assert starcount_module.calculate_starcount_outcome(np.zeros((0, 0)))["outcome"] == "measurement_failure"


def test_wrapper_returns_none_on_failure_never_zero():
    flat = np.full((120, 120), 5.0)
    assert starcount_module.calculate_starcount(flat) is None

    # genuine no-detections still yields integer 0 through the wrapper
    rng = np.random.default_rng(11)
    assert starcount_module.calculate_starcount(rng.normal(0.0, 1.0, (160, 160))) == 0

    # real detections yield the integer count
    assert starcount_module.calculate_starcount(gaussian_field()) > 0


# --- worker path ------------------------------------------------------------

def test_worker_populates_outcome_and_error(tmp_path):
    path = _write_fits(tmp_path / "light.fit", gaussian_field())
    result = analyse_logic._snr_worker(str(path))
    assert result["error"] is None
    assert result["starcount_outcome"] == "ok"
    assert result["starcount"] > 0
    assert result["starcount_error"] is None
    assert np.isfinite(result["snr"])


def test_worker_starcount_failure_keeps_valid_snr(tmp_path, monkeypatch):
    path = _write_fits(tmp_path / "light.fit", gaussian_field())

    def _fail(*_a, **_k):
        return {
            "outcome": "measurement_failure",
            "count": None,
            "reason": "injected starcount failure",
        }

    monkeypatch.setattr(
        analyse_logic.starcount_module, "calculate_starcount_outcome", _fail
    )
    result = analyse_logic._snr_worker(str(path))

    assert result["error"] is None
    assert np.isfinite(result["snr"])
    assert result["starcount"] is None
    assert result["starcount_outcome"] == "measurement_failure"
    assert "injected starcount failure" in result["starcount_error"]


def test_worker_unavailable_state_when_module_missing(tmp_path, monkeypatch):
    path = _write_fits(tmp_path / "light.fit", gaussian_field())
    monkeypatch.setattr(analyse_logic, "starcount_module", None)
    result = analyse_logic._snr_worker(str(path))
    assert result["starcount"] is None
    assert result["starcount_outcome"] == "unavailable"
    assert result["starcount_error"] is None


# --- aggregation ------------------------------------------------------------

def test_aggregation_pool_branch_single_bounded_log(tmp_path, monkeypatch):
    for idx in range(4):
        (tmp_path / f"light_{idx}.fit").touch()
    logs = []
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _StarcountFailureExecutor,
    )
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _recording_callbacks(logs),
    )

    summaries = [e for e in logs if e[0] == "logic_starcount_measurement_failures"]
    assert len(summaries) == 1
    key, kwargs = summaries[0]
    assert kwargs["count"] == 4
    assert kwargs["file"]
    assert "statistics" in kwargs["reason"]
    # no per-image tracebacks / file errors
    assert not [e for e in logs if e[0] == "logic_file_error"]
    assert all(r["status"] == "ok" for r in rows)
    assert all(np.isfinite(r["snr"]) for r in rows)


def test_aggregation_sequential_fallback_matches_pool(tmp_path, monkeypatch):
    paths = []
    for idx in range(3):
        paths.append(_write_fits(tmp_path / f"light_{idx}.fit", gaussian_field(seed=idx)))

    def _fail(*_a, **_k):
        return {
            "outcome": "measurement_failure",
            "count": None,
            "reason": "injected starcount failure",
        }

    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ProcessPoolExecutor", _RaisingExecutor
    )
    monkeypatch.setattr(
        analyse_logic.starcount_module, "calculate_starcount_outcome", _fail
    )

    logs = []
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _recording_callbacks(logs),
    )

    assert [e[0] for e in logs].count("logic_snr_pool_fallback") == 1
    summaries = [e for e in logs if e[0] == "logic_starcount_measurement_failures"]
    assert len(summaries) == 1
    assert summaries[0][1]["count"] == len(paths)
    assert "injected starcount failure" in summaries[0][1]["reason"]
    assert all(r["status"] == "ok" for r in rows)
    assert all(r["starcount"] is None for r in rows)
    assert all(r["starcount_outcome"] == "measurement_failure" for r in rows)


def test_fallback_does_not_double_count_pool_starcount_failures(tmp_path, monkeypatch):
    paths = []
    for idx in range(3):
        paths.append(_write_fits(tmp_path / f"light_{idx}.fit", gaussian_field(seed=idx)))

    def _fail(*_a, **_k):
        return {
            "outcome": "measurement_failure",
            "count": None,
            "reason": "injected starcount failure",
        }

    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ProcessPoolExecutor", _CountThenRaiseExecutor
    )
    monkeypatch.setattr(
        analyse_logic.starcount_module, "calculate_starcount_outcome", _fail
    )

    logs = []
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _recording_callbacks(logs),
    )

    assert [e[0] for e in logs].count("logic_snr_pool_fallback") == 1
    summaries = [e for e in logs if e[0] == "logic_starcount_measurement_failures"]
    assert len(summaries) == 1
    assert summaries[0][1]["count"] == len(paths), "pool failures double counted by fallback"
    assert all(r["status"] == "ok" for r in rows)


# --- failure must never become rejection / action ---------------------------

def test_starcount_failure_never_rejected_by_threshold(tmp_path, monkeypatch):
    for idx in range(2):
        (tmp_path / f"light_{idx}.fit").touch()
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _StarcountFailureExecutor,
    )
    logs = []
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, starcount_threshold=10),
        _recording_callbacks(logs),
    )

    for r in rows:
        # starcount failure must not become a rejection/action
        assert r["starcount"] is None
        assert r["rejected_reason"] != "starcount_pending_action"
        assert r["action"] != "pending_starcount_action"
        assert r["status"] == "ok"
        assert np.isfinite(r["snr"])


def test_genuine_zero_starcount_is_numeric_value():
    # A true no-detection image has a real numeric 0, distinct from None failure.
    rng = np.random.default_rng(5)
    outcome = starcount_module.calculate_starcount_outcome(rng.normal(0.0, 1.0, (160, 160)))
    assert outcome["outcome"] == "no_detections"
    assert outcome["count"] == 0
    assert outcome["count"] is not None


# --- schema + persistence ---------------------------------------------------

def test_schema_includes_starcount_outcome_and_error():
    keys = analysis_schema.get_result_keys()
    assert "starcount" in keys
    assert "starcount_outcome" in keys
    assert "starcount_error" in keys


# --- Qt recommendation with starcount failure ------------------------------

@pytest.mark.skipif(
    not _qt_available(), reason="PySide6 not available"
)
def test_qt_recommendation_ignores_starcount_failure(monkeypatch):
    import zeanalyser.analyse_gui_qt as gui_mod

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("MPLBACKEND", "Agg")

    created_app = False
    app = gui_mod.QApplication.instance()
    if app is None:
        app = gui_mod.QApplication([])
        created_app = True

    win = gui_mod.ZeAnalyserMainWindow()
    try:
        # A measurement failure (starcount None) with otherwise valid metrics
        # must not raise TypeError and must be eligible on its other metrics;
        # a genuine numeric 0 must participate in the percentile threshold.
        rows = [
            {
                "file": "failed.fits", "rel_path": "failed.fits",
                "path": "/data/failed.fits", "status": "ok", "action": "kept",
                "rejected_reason": None, "snr": 30.0, "fwhm": 1.5, "ecc": 0.2,
                "starcount": None, "starcount_outcome": "measurement_failure",
                "starcount_error": "injected starcount failure",
            },
            {
                "file": "zero.fits", "rel_path": "zero.fits",
                "path": "/data/zero.fits", "status": "ok", "action": "kept",
                "rejected_reason": None, "snr": 30.0, "fwhm": 1.5, "ecc": 0.2,
                "starcount": 0, "starcount_outcome": "no_detections",
                "starcount_error": None,
            },
            {
                "file": "many.fits", "rel_path": "many.fits",
                "path": "/data/many.fits", "status": "ok", "action": "kept",
                "rejected_reason": None, "snr": 30.0, "fwhm": 1.5, "ecc": 0.2,
                "starcount": 150, "starcount_outcome": "ok",
                "starcount_error": None,
            },
        ]
        win.set_results(rows)
        win.reco_snr_pct_min = 25.0
        win.reco_fwhm_pct_max = 75.0
        win.reco_ecc_pct_max = 75.0
        win.reco_starcount_pct_min = 25.0
        win.use_starcount_filter = True

        # must not raise TypeError
        recos, snr_p, fwhm_p, ecc_p, sc_p = win._compute_recommended_subset()

        # The failure row is eligible via its other metrics (neutral semantics).
        files = [r["file"] for r in recos]
        assert "failed.fits" in files
        # A genuine numeric 0 participates in the percentile: with the 25th
        # percentile above 0, the zero-count image falls below the threshold
        # and is excluded, while the 150-count image remains.
        assert "zero.fits" not in files
        assert "many.fits" in files
        # sc_p is computed only from numeric counts (None excluded).
        assert sc_p is not None and gui_mod.is_finite_number(sc_p)
        # The true zero is a real numeric value (0 <= sc_p when percentile > 0).
        assert 0 < sc_p
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_starcount_failure_persisted_in_json_block(tmp_path, monkeypatch):
    for idx in range(2):
        (tmp_path / f"light_{idx}.fit").touch()
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _StarcountFailureExecutor,
    )
    log_path = str(tmp_path / project_state.DEFAULT_LOG_FILENAME)
    analyse_logic.perform_analysis(
        str(tmp_path), log_path, _options(tmp_path), _recording_callbacks([])
    )

    # Real reopen API: stream and parse the last complete valid visualization
    # block exactly as the Qt model does on project reopen.
    rows = project_state.load_latest_valid_visualization_block(log_path)

    assert rows is not None
    assert len(rows) == 2
    for r in rows:
        assert r["starcount"] is None
        assert r["starcount_outcome"] == "measurement_failure"
        assert r["starcount_error"]
