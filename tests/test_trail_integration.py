"""TRAIL-01 integration tests for the acstools satellite-trail path.

Covers the end-to-end repair: canonical parameters + deterministic legacy
migration, the single result/error key-normalization primitive (fail-safe for
invalid extensions and string sentinels), multi-extension aggregation, real
``perform_analysis`` with injected acstools (positive/negative/file-error/
missing/malformed/upstream-skip), canonical states + legacy aliases + actions
(deferred and immediate), reopen/filter/visualization fail-safe behaviour, and
the acstools ``(filename, 0)`` return shape (no mock that bypasses
normalization).
"""
from __future__ import annotations

import json
import os
import glob
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from zeanalyser import analyse_logic, analysis_schema, project_state
from zeanalyser import trail_module


def _qt_available() -> bool:
    try:
        import zeanalyser.analyse_gui_qt as gui_mod
        return gui_mod.QApplication is not object
    except Exception:
        return False


# --- helpers -----------------------------------------------------------------

def gaussian_field(seed: int = 7, shape: tuple[int, int] = (64, 64)):
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, shape)


def _write_fits(path: Path, data: np.ndarray) -> Path:
    fits.PrimaryHDU(data=data.astype(np.float32)).writeto(str(path))
    return path


def _snr_ok_result(path: str) -> dict:
    return {
        "path": path,
        "snr": 20.0,
        "sky_bg": 1.0,
        "sky_noise": 1.0,
        "signal_pixels": 10,
        "starcount": 5,
        "starcount_outcome": "ok",
        "starcount_error": None,
        "exposure": 10.0,
        "filter": "LP",
        "temperature": 0.0,
        "eqmode": 2,
        "sitelong": None,
        "sitelat": None,
        "telescope": "Seestar",
        "date_obs": "2026-09-14T00:00:00",
        "error": None,
        "fwhm": 2.0,
        "ecc": 0.5,
        "n_star_ecc": 5,
        "fwhm_ecc_outcome": "ok",
        "fwhm_ecc_error": None,
        "ra": None,
        "dec": None,
    }


class _ImmediateSNRExecutor:
    """ProcessPoolExecutor stand-in returning a canned OK result per file."""

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, _function, path):
        future = Future()
        future.set_result(_snr_ok_result(path))
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


class _ImmediateTrailExecutor:
    """ThreadPoolExecutor stand-in running the worker synchronously."""

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - defensive
            future.set_exception(exc)
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


class _FakeSatdet:
    """Injected acstools.satdet.

    Returns acstools-shaped ``(filename, ext)`` keys, but — like the real
    ``detsat`` — only the entries matching the *current* ``searchpattern``.
    This keeps the tuple-key normalization honest instead of handing back the
    whole dict for every file.
    """

    def __init__(self, results, errors):
        self.results = dict(results)
        self.errors = dict(errors)
        self.calls = []

    def _matches(self, key_path, searchpattern):
        expected = os.path.normcase(os.path.abspath(str(key_path)))
        return any(
            expected == os.path.normcase(os.path.abspath(candidate))
            for candidate in glob.glob(str(searchpattern))
        )

    def detsat(self, searchpattern, chips=None, n_processes=None, sigma=None,
               low_thresh=None, h_thresh=None, small_edge=None, line_len=None,
               line_gap=None, percentile=None, buf=None, plot=False, verbose=False):
        self.calls.append({
            "searchpattern": searchpattern,
            "chips": chips,
            "n_processes": n_processes,
            "sigma": sigma,
            "low_thresh": low_thresh,
            "h_thresh": h_thresh,
            "small_edge": small_edge,
            "line_len": line_len,
            "line_gap": line_gap,
        })
        results = {k: v for k, v in self.results.items() if self._matches(k[0], searchpattern)}
        errors = {k: v for k, v in self.errors.items() if self._matches(k[0], searchpattern)}
        return results, errors


def _patch_trail_available(monkeypatch):
    monkeypatch.setattr(trail_module, "SATDET_AVAILABLE", True)
    monkeypatch.setattr(trail_module, "SATDET_USES_SEARCHPATTERN", True)
    monkeypatch.setattr(trail_module, "SCIPY_AVAILABLE", True)
    monkeypatch.setattr(trail_module, "SKIMAGE_AVAILABLE", True)
    monkeypatch.setattr(analyse_logic, "SATDET_AVAILABLE", True)
    monkeypatch.setattr(analyse_logic, "TRAIL_MODULE_LOADED", True)


def _patch_executors(monkeypatch):
    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateSNRExecutor
    )
    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ThreadPoolExecutor", _ImmediateTrailExecutor
    )


def _options(root: Path, **overrides):
    options = {
        "include_subfolders": False,
        "analyze_snr": False,
        "detect_trails": True,
        "move_rejected": False,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(root),
    }
    options.update(overrides)
    return options


def _callbacks(logs=None):
    logs = logs if logs is not None else []
    return {
        "is_cancelled": lambda: False,
        "progress": lambda *_a, **_k: None,
        "status": lambda *_a, **_k: None,
        "log": lambda key, **kw: logs.append((key, kw)),
    }


# --- A. Parameters -----------------------------------------------------------

def test_run_trail_detection_passes_exact_kwargs(monkeypatch):
    fake = _FakeSatdet({}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)

    params = {
        "low_thresh": 0.2, "h_thresh": 0.6, "sigma": 1.7,
        "line_len": 120, "small_edge": 33, "line_gap": 17,
    }
    trail_module.run_trail_detection(["/tmp/a.fits"], params)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["low_thresh"] == 0.2
    assert call["h_thresh"] == 0.6
    assert call["sigma"] == 1.7
    assert call["line_len"] == 120
    assert call["small_edge"] == 33
    assert call["line_gap"] == 17
    assert call["chips"] == [0]
    assert call["n_processes"] == 1
    assert call["searchpattern"] == "/tmp/a.fits"


def test_run_trail_detection_escapes_literal_glob_characters(tmp_path, monkeypatch):
    path = tmp_path / "literal[1].fits"
    path.touch()
    key = (str(path), 0)
    fake = _FakeSatdet({key: []}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)

    results, errors = trail_module.run_trail_detection(
        [str(path)], {"low_thresh": 0.1, "h_thresh": 0.5}
    )

    assert errors == {}
    assert key in results
    assert fake.calls[0]["searchpattern"] == glob.escape(str(path))


def test_run_trail_detection_legacy_migration_logged(monkeypatch):
    fake = _FakeSatdet({}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)

    logs = []
    trail_module.run_trail_detection(
        "/tmp/*.fits", {"low_thr": 12.5, "high_thr": 65.0},
        log_callback=lambda k, **kw: logs.append((k, kw)),
    )

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["low_thresh"] == pytest.approx(0.125)
    assert call["h_thresh"] == pytest.approx(0.65)
    migrations = [e for e in logs if e[0] == "logic_trail_threshold_legacy_migration"]
    assert len(migrations) == 2  # low and high


@pytest.mark.parametrize("bad_params", [
    {"low_thresh": 0.2, "low_thr": 20},           # ambiguous canonical + legacy
    {"low_thresh": 1.5, "h_thresh": 0.5},         # canonical out of range
    {"low_thr": 150, "high_thr": 50},             # legacy out of range
    {"low_thresh": 0.6, "h_thresh": 0.2},         # low > high
])
def test_run_trail_detection_blocks_invalid_config(monkeypatch, bad_params):
    fake = _FakeSatdet({}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)

    results, errors = trail_module.run_trail_detection("/tmp/*.fits", bad_params)

    assert results == {}
    assert ("CONFIG_ERROR", 0) in errors
    assert len(fake.calls) == 0  # acstools never called


# --- B. Key normalization ----------------------------------------------------

def test_normalize_detsat_key_forms():
    abs_norm = os.path.normcase(os.path.abspath("/abs/file.fits"))

    assert trail_module.normalize_detsat_key(("/abs/file.fits", 0)) == (abs_norm, 0)
    assert trail_module.normalize_detsat_key("/abs/file.fits") == (abs_norm, 0)
    # extension coerced to int when convertible
    assert trail_module.normalize_detsat_key(("/abs/file.fits", "0")) == (abs_norm, 0)
    # relative path becomes absolute + normcase
    key = trail_module.normalize_detsat_key(("relative/file.fits", 0))
    assert key[0] == os.path.normcase(os.path.abspath("relative/file.fits"))
    assert key[1] == 0
    # uninterpretable keys -> None
    assert trail_module.normalize_detsat_key(None) is None
    assert trail_module.normalize_detsat_key(123) is None
    # non-convertible extension -> None (never coerced to 0)
    assert trail_module.normalize_detsat_key(("/abs/file.fits", "SCI")) is None
    # path robustness: None/empty/non-str path never maps to cwd/... or None
    assert trail_module.normalize_detsat_key((None, 0)) is None
    assert trail_module.normalize_detsat_key(("", 0)) is None
    assert trail_module.normalize_detsat_key(("   ", 0)) is None
    assert trail_module.normalize_detsat_key((123, 0)) is None


def test_is_global_error_key_and_segments_serializable():
    assert trail_module.is_global_error_key(("CONFIG_ERROR", 0)) is True
    assert trail_module.is_global_error_key(("FATAL_ERROR", 0)) is True
    assert trail_module.is_global_error_key("CONFIG_ERROR") is True  # string sentinel
    assert trail_module.is_global_error_key("config_error") is True  # case-insensitive
    assert trail_module.is_global_error_key(("/real/file.fits", 0)) is False
    assert trail_module.is_global_error_key("/real/file.fits") is False

    segs, err = trail_module.segments_to_serializable(
        np.array([[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]])
    )
    assert err is None
    assert segs == [[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]]
    assert trail_module.segments_to_serializable(np.empty(0)) == ([], None)
    # None payload is a missing result, never a measured negative
    assert trail_module.segments_to_serializable(None) == ([], "trail result is None (missing payload)")
    # malformed (non-empty but not 2x2) -> error, not silent negative
    segs, err = trail_module.segments_to_serializable([[1, 2, 3]])
    assert err is not None
    assert segs == []


def test_segments_payload_strict():
    # string / scalar payloads are never a measured negative
    segs, err = trail_module.segments_to_serializable("abc")
    assert err is not None and segs == []
    segs, err = trail_module.segments_to_serializable(123)
    assert err is not None and segs == []
    # non-numeric coordinates
    segs, err = trail_module.segments_to_serializable([[["a", 0.0], [1.0, 1.0]]])
    assert err is not None and segs == []
    # non-finite coordinates (NaN / Inf)
    segs, err = trail_module.segments_to_serializable([[[float("nan"), 0.0], [1.0, 1.0]]])
    assert err is not None and segs == []
    segs, err = trail_module.segments_to_serializable([[[float("inf"), 0.0], [1.0, 1.0]]])
    assert err is not None and segs == []
    # explicitly empty container remains a valid measured negative
    assert trail_module.segments_to_serializable([]) == ([], None)


def test_bound_message():
    assert trail_module.bound_message(None) is None
    assert trail_module.bound_message("short") == "short"
    long = "x" * 600
    bounded = trail_module.bound_message(long)
    assert len(bounded) == 500
    assert bounded.endswith("...")


# --- C/F. End-to-end perform_analysis with injected acstools -----------------

def _run_trail_analysis(tmp_path, monkeypatch, results_by_abs, errors_by_abs,
                        **opt_overrides):
    fake = _FakeSatdet(results_by_abs, errors_by_abs)
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    logs = []
    options = dict(opt_overrides)
    options.setdefault('trail_params', {"low_thresh": 0.1, "h_thresh": 0.5})
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, **options),
        _callbacks(logs),
    )
    return rows, fake, logs


def test_perform_analysis_trail_states_and_immediate_action(tmp_path, monkeypatch):
    names = ["pos.fit", "neg.fit", "err.fit", "missing.fit"]
    for name in names:
        _write_fits(tmp_path / name, gaussian_field(seed=abs(hash(name)) % 100))

    pos_abs = str(tmp_path / "pos.fit")
    neg_abs = str(tmp_path / "neg.fit")
    err_abs = str(tmp_path / "err.fit")

    # acstools return shape: (filename, ext=0) tuple keys.
    results = {
        (pos_abs, 0): [[[10.0, 20.0], [30.0, 40.0]], [[50.0, 60.0], [70.0, 80.0]]],
        (neg_abs, 0): [],
    }
    errors = {(err_abs, 0): "synthetic processing error"}

    reject_dir = tmp_path / "rejected_trails"
    rows, fake, _ = _run_trail_analysis(
        tmp_path, monkeypatch, results, errors,
        move_rejected=True, trail_reject_dir=str(reject_dir),
        apply_trail_action_immediately=True,
    )

    by_file = {r["file"]: r for r in rows}
    assert set(by_file) == set(names)

    # positive: tuple key found even though the orchestrator fed a list.
    p = by_file["pos.fit"]
    assert p["trail_state"] == "measured_positive"
    assert p["has_trails"] is True
    assert p["num_trails"] == 2
    assert p["trail_segment_count"] == 2
    assert len(p["trail_segments"]) == 2
    assert p["trail_backend_id"] == "acstools.satdet"
    assert p["trail_parameters_effective"]["low_thresh"] == 0.1
    assert p["rejected_reason"] == "trail"
    assert p["action"] == "moved_trail"
    assert not (tmp_path / "pos.fit").exists()
    assert (reject_dir / "pos.fit").exists()

    # negative
    n = by_file["neg.fit"]
    assert n["trail_state"] == "measured_negative"
    assert n["has_trails"] is False
    assert n["num_trails"] == 0
    assert n["trail_segment_count"] == 0
    assert n["trail_segments"] == []
    assert n["rejected_reason"] is None
    assert n["action"] == "kept"

    # file error -> measurement_failure, never negative, never actioned
    e = by_file["err.fit"]
    assert e["trail_state"] == "measurement_failure"
    assert e["has_trails"] is None
    assert e["trail_error"] == "synthetic processing error"
    assert e["num_trails"] is None
    assert e["trail_segments"] is None
    assert e["trail_segment_count"] is None
    assert e["rejected_reason"] is None
    assert e["action"] == "kept"
    assert (tmp_path / "err.fit").exists()

    # missing output -> indeterminate, never negative, never actioned
    m = by_file["missing.fit"]
    assert m["trail_state"] == "indeterminate"
    assert m["has_trails"] is None
    assert m["num_trails"] is None
    assert m["trail_segments"] is None
    assert m["trail_segment_count"] is None
    assert m["rejected_reason"] is None
    assert m["action"] == "kept"
    assert (tmp_path / "missing.fit").exists()


def test_perform_analysis_trail_deferred_action(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    results = {(pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]]}
    errors = {}

    reject_dir = tmp_path / "rejected_trails"
    rows, fake, _ = _run_trail_analysis(
        tmp_path, monkeypatch, results, errors,
        move_rejected=True, trail_reject_dir=str(reject_dir),
        apply_trail_action_immediately=False,
    )

    assert len(rows) == 1
    p = rows[0]
    assert p["trail_state"] == "measured_positive"
    assert p["has_trails"] is True
    assert p["rejected_reason"] == "trail_pending_action"
    assert p["action"] == "pending_trail_action"
    assert (tmp_path / "pos.fit").exists()  # deferred: source untouched


def test_perform_analysis_global_config_error_is_unavailable(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    # invalid threshold config -> run_trail_detection returns CONFIG_ERROR
    # without calling acstools; every eligible file becomes unavailable, and
    # the real config message is preserved (not a generic one).
    fake = _FakeSatdet({}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, trail_params={"low_thresh": 0.9, "h_thresh": 0.1}),
        _callbacks(),
    )

    assert len(fake.calls) == 0
    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "unavailable"
    assert r["has_trails"] is None
    assert "low_thresh=0.9 > h_thresh=0.1" in r["trail_reason"]
    assert r["rejected_reason"] is None
    assert r["action"] == "kept"


def test_perform_analysis_multi_ext_aggregated(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    # same file, two extensions -> segments aggregated deterministically
    results = {
        (pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]],
        (pos_abs, 1): [[[2.0, 2.0], [3.0, 3.0]]],
    }
    rows, fake, _ = _run_trail_analysis(tmp_path, monkeypatch, results, {})

    assert len(rows) == 1
    p = rows[0]
    assert p["trail_state"] == "measured_positive"
    assert p["trail_segment_count"] == 2
    assert len(p["trail_segments"]) == 2


def test_perform_analysis_malformed_result_is_indeterminate(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    # non-empty but malformed result must NOT become a measured negative
    results = {(pos_abs, 0): [[1, 2, 3]]}
    rows, fake, _ = _run_trail_analysis(tmp_path, monkeypatch, results, {})

    assert len(rows) == 1
    p = rows[0]
    assert p["trail_state"] == "indeterminate"
    assert p["has_trails"] is None
    assert p["num_trails"] is None
    assert p["trail_error"] == "malformed trail segment in result"
    assert p["rejected_reason"] is None


def test_perform_analysis_invalid_ext_ignored_fail_safe(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    # a result on a non-convertible extension is ignored, never coerced to ext0
    results = {(pos_abs, "SCI"): [[[0.0, 0.0], [1.0, 1.0]]]}
    rows, fake, _ = _run_trail_analysis(tmp_path, monkeypatch, results, {})

    assert len(rows) == 1
    p = rows[0]
    # no valid result for the file -> indeterminate (missing), never negative
    assert p["trail_state"] == "indeterminate"
    assert p["has_trails"] is None


def test_perform_analysis_legacy_params_effective(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    results = {(pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]]}
    rows, fake, _ = _run_trail_analysis(
        tmp_path, monkeypatch, results, {},
        trail_params={"low_thr": 10, "high_thr": 50},
    )

    assert len(rows) == 1
    p = rows[0]
    assert p["trail_state"] == "measured_positive"
    # effective params carry canonical fractions, legacy migrated
    assert p["trail_parameters_effective"]["low_thresh"] == pytest.approx(0.1)
    assert p["trail_parameters_effective"]["h_thresh"] == pytest.approx(0.5)


def test_legacy_migration_reaches_official_log(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    fake = _FakeSatdet({(pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]]}, {})
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    logs = []
    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, trail_params={"low_thr": 10, "high_thr": 50}),
        _callbacks(logs),
    )

    # migration journalisée via le log officiel (et non stdout)
    migrations = [e for e in logs if e[0] == "logic_trail_threshold_legacy_migration"]
    assert len(migrations) == 2
    # workers reçoivent le dict effectif canonique (.1/.5)
    assert len(fake.calls) == 1
    assert fake.calls[0]["low_thresh"] == pytest.approx(0.1)
    assert fake.calls[0]["h_thresh"] == pytest.approx(0.5)
    # per-row / summary effective params canoniques
    assert rows[0]["trail_state"] == "measured_positive"
    assert rows[0]["trail_parameters_effective"]["low_thresh"] == pytest.approx(0.1)
    assert rows[0]["trail_parameters_effective"]["h_thresh"] == pytest.approx(0.5)


def test_global_error_dominates_result_tuple(tmp_path, monkeypatch):
    # A run yielding BOTH a global error and a per-file result is non-probative
    # (no per-chunk provenance), never measured positive/negative.
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    def fake_run(search_pattern, params, **kw):
        return {(pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]]}, {("FATAL_ERROR", 0): "boom"}

    monkeypatch.setattr(trail_module, "run_trail_detection", fake_run)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path), str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path), _callbacks(),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "measurement_failure"
    assert r["has_trails"] is None
    assert r["trail_error"] == "boom"
    assert r["rejected_reason"] is None
    assert r["action"] == "kept"


def test_global_error_dominates_result_string(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    def fake_run(search_pattern, params, **kw):
        return {(pos_abs, 0): [[[0.0, 0.0], [1.0, 1.0]]]}, {"CONFIG_ERROR": "bad config"}

    monkeypatch.setattr(trail_module, "run_trail_detection", fake_run)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path), str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path), _callbacks(),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "unavailable"
    assert r["has_trails"] is None
    assert r["trail_reason"] == "bad config"
    assert r["rejected_reason"] is None


def test_normalized_key_collision_is_indeterminate(tmp_path, monkeypatch):
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    def fake_run(search_pattern, params, **kw):
        # string key + tuple ext0 key both normalize to (pos_abs, 0)
        return {
            pos_abs: [[[0.0, 0.0], [1.0, 1.0]]],
            (pos_abs, 0): [[[2.0, 2.0], [3.0, 3.0]]],
        }, {}

    monkeypatch.setattr(trail_module, "run_trail_detection", fake_run)
    _patch_trail_available(monkeypatch)
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path), str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path), _callbacks(),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "indeterminate"
    assert "collision" in r["trail_reason"]
    assert r["has_trails"] is None
    assert r["rejected_reason"] is None


def test_none_payload_is_indeterminate_not_negative(tmp_path, monkeypatch):
    # A result payload of None (not an empty container) is never measured negative.
    _write_fits(tmp_path / "pos.fit", gaussian_field())
    pos_abs = str(tmp_path / "pos.fit")

    results = {(pos_abs, 0): None}
    rows, fake, _ = _run_trail_analysis(tmp_path, monkeypatch, results, {})

    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "indeterminate"
    assert r["has_trails"] is None
    assert "missing payload" in r["trail_error"]


# --- D. Reopen / filter / visualization --------------------------------------

def _trail_rows():
    return [
        {"file": "a.fits", "path": "/d/a.fits", "snr": 10.0,
         "trail_state": "measured_positive", "has_trails": True,
         "num_trails": 2, "trail_segments": [[[0.0, 0.0], [1.0, 1.0]]],
         "trail_reason": None, "trail_error": None,
         "trail_segment_count": 2, "trail_backend_id": "acstools.satdet",
         "trail_parameters_effective": {"low_thresh": 0.1, "h_thresh": 0.5}},
        {"file": "b.fits", "path": "/d/b.fits", "snr": 10.0,
         "trail_state": "measured_negative", "has_trails": False,
         "num_trails": 0, "trail_segments": []},
        {"file": "c.fits", "path": "/d/c.fits", "snr": 10.0,
         "trail_state": "indeterminate", "has_trails": None,
         "num_trails": None, "trail_segments": None},
        {"file": "d.fits", "path": "/d/d.fits", "snr": 10.0,
         "trail_state": "measurement_failure", "has_trails": None,
         "num_trails": None, "trail_error": "boom"},
        {"file": "e.fits", "path": "/d/e.fits", "snr": 10.0,
         "trail_state": "unavailable", "has_trails": None,
         "num_trails": None},
    ]


def test_reopen_preserves_trail_fields(tmp_path, monkeypatch):
    if not _qt_available():
        pytest.skip("PySide6 unavailable")
    import zeanalyser.analyse_gui_qt as gui_mod
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    rows = _trail_rows()
    log_path = tmp_path / "analyse_resultats.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("--- BEGIN VISUALIZATION DATA ---\n")
        json.dump(rows, fh)
        fh.write("\n--- END VISUALIZATION DATA ---\n")

    created = False
    app = gui_mod.QApplication.instance()
    if app is None:
        app = gui_mod.QApplication([])
        created = True
    win = gui_mod.ZeAnalyserMainWindow()
    try:
        assert win._load_visualisation_from_log_path(str(log_path)) is True
        loaded = win._get_analysis_results_rows()
        assert len(loaded) == len(rows)
        by_file = {r["file"]: r for r in loaded}
        assert by_file["a.fits"]["trail_state"] == "measured_positive"
        assert by_file["a.fits"]["trail_segments"] == [[[0.0, 0.0], [1.0, 1.0]]]
        assert by_file["a.fits"]["trail_parameters_effective"]["low_thresh"] == 0.1
        assert by_file["b.fits"]["trail_state"] == "measured_negative"
        assert by_file["d.fits"]["trail_error"] == "boom"
        assert by_file["c.fits"]["num_trails"] is None
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created:
            app.quit()


def test_filter_yes_no_exclude_unknown_states(monkeypatch):
    if not _qt_available():
        pytest.skip("PySide6 unavailable")
    import zeanalyser.analyse_gui_qt as gui_mod
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created = False
    app = gui_mod.QApplication.instance()
    if app is None:
        app = gui_mod.QApplication([])
        created = True

    win = gui_mod.ZeAnalyserMainWindow()
    try:
        win.set_results(_trail_rows())
        proxy = win._results_proxy

        def filtered_files():
            names = []
            for i in range(proxy.rowCount()):
                src = proxy.mapToSource(proxy.index(i, 0))
                names.append(win._results_model.get_row(src.row())["file"])
            return names

        win.has_trails_box.setCurrentText("Any")
        app.processEvents()
        assert len(filtered_files()) == 5

        win.has_trails_box.setCurrentText("Yes")
        app.processEvents()
        assert filtered_files() == ["a.fits"]

        win.has_trails_box.setCurrentText("No")
        app.processEvents()
        assert filtered_files() == ["b.fits"]
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created:
            app.quit()


def test_visualization_never_counts_unknown_as_negative():
    import zeanalyser.analyse_gui_qt as gui_mod

    rows = _trail_rows()
    pos, neg = gui_mod.count_trail_states(rows)
    assert pos == 1  # a.fits only
    assert neg == 1  # b.fits only

    # legacy boolean rows without trail_state -> indeterminate, not negative
    legacy = [{"file": "x", "has_trails": False}, {"file": "y", "has_trails": True}]
    pos2, neg2 = gui_mod.count_trail_states(legacy)
    assert pos2 == 0
    assert neg2 == 0


# --- E. Legacy bool without state -> indeterminate in new consumers ----------

def test_legacy_bool_without_state_is_indeterminate():
    assert analysis_schema.resolve_trail_state({"has_trails": False}) == "indeterminate"
    assert analysis_schema.resolve_trail_state({"has_trails": True}) == "indeterminate"
    assert analysis_schema.resolve_trail_state({}) == "indeterminate"
    assert analysis_schema.resolve_trail_state(None) == "indeterminate"
    # explicit states pass through
    assert analysis_schema.resolve_trail_state({"trail_state": "measured_negative"}) == "measured_negative"
    # alias mapping
    assert analysis_schema.has_trails_alias("measured_positive") is True
    assert analysis_schema.has_trails_alias("measured_negative") is False
    assert analysis_schema.has_trails_alias("indeterminate") is None
    assert analysis_schema.has_trails_alias("unavailable") is None


def test_detection_disabled_is_skipped(tmp_path, monkeypatch):
    _write_fits(tmp_path / "light.fit", gaussian_field())
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, detect_trails=False),
        _callbacks(),
    )

    assert len(rows) == 1
    r = rows[0]
    assert r["trail_state"] == "skipped"
    assert r["has_trails"] is None
    assert r["num_trails"] is None
    assert r["trail_segments"] is None
    assert r["trail_segment_count"] is None
    assert r["rejected_reason"] is None


def test_upstream_rejected_files_are_explicitly_skipped(tmp_path, monkeypatch):
    # A file rejected by starcount threshold never reaches trail detection and
    # must be marked skipped (upstream_selection), not indeterminate.
    _write_fits(tmp_path / "light.fit", gaussian_field())
    _patch_executors(monkeypatch)

    rows = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path, analyze_snr=True, starcount_threshold=99999),
        _callbacks(),
    )

    assert len(rows) == 1
    r = rows[0]
    # starcount (5) < threshold (99999) -> upstream reject, never trail-measured
    assert r["trail_state"] == "skipped"
    assert "upstream_selection" in r["trail_reason"]
    assert r["has_trails"] is None
    assert r["num_trails"] is None
    assert r["trail_segments"] is None


# --- REWORK-3 -----------------------------------------------------------------

def test_payloads_equal_robust():
    pe = analyse_logic.payloads_equal

    # identical / different nested lists
    assert pe([[1, 2], [3, 4]], [[1, 2], [3, 4]]) is True
    assert pe([[1, 2], [3, 4]], [[1, 2], [3, 5]]) is False
    # ragged lists must not raise
    assert pe([[1, 2], [3]], [[1, 2], [3]]) is True
    assert pe([[1, 2], [3]], [[1, 2], [4]]) is False
    # numpy arrays (shape + array_equal)
    assert pe(np.array([[1, 2]]), np.array([[1, 2]])) is True
    assert pe(np.array([[1, 2]]), np.array([[1, 3]])) is False
    # ragged with ndarray elements
    assert pe([np.array([1, 2]), np.array([3])], [np.array([1, 2]), np.array([4])]) is False
    # scalars
    assert pe(1, 1) is True
    assert pe(1, 2) is False
    assert pe(1.0, 1.0) is True
    # explicit NaN policy (equal_nan=True)
    assert pe(np.array([float("nan")]), np.array([float("nan")])) is True
    # list vs tuple of same values
    assert pe([1, 2], (1, 2)) is True
    # mappings
    assert pe({"a": 1}, {"a": 1}) is True
    assert pe({"a": 1}, {"a": 2}) is False

    # object whose __eq__ returns an ndarray -> never raises
    class Weird:
        def __eq__(self, other):
            return np.array([True, False])

    assert pe(Weird(), Weird()) is False

    # object whose __eq__ raises -> never raises
    class Boom:
        def __eq__(self, other):
            raise ValueError("nope")

    assert pe(Boom(), Boom()) is False


def test_shared_count_and_activity_helpers():
    rows = [
        {"trail_state": "measured_positive", "has_trails": True},
        {"trail_state": "measured_negative", "has_trails": False},
        {"trail_state": "indeterminate", "has_trails": None},
        {"trail_state": "measurement_failure", "has_trails": None},
        {"trail_state": "skipped", "has_trails": None},
        {"trail_state": "unavailable", "has_trails": None},
    ]
    assert analysis_schema.count_trail_states(rows) == (1, 1)
    assert analysis_schema.has_measured_or_attempted_trail_state(rows) is True

    # skipped/unavailable-only -> inactive, never counted
    skipped_only = [{"trail_state": "skipped"}, {"trail_state": "unavailable"}]
    assert analysis_schema.count_trail_states(skipped_only) == (0, 0)
    assert analysis_schema.has_measured_or_attempted_trail_state(skipped_only) is False

    # legacy bool without state -> indeterminate, not counted as negative
    legacy = [{"has_trails": False}, {"has_trails": True}]
    assert analysis_schema.count_trail_states(legacy) == (0, 0)
    assert analysis_schema.resolve_trail_state({"has_trails": False}) == "indeterminate"


@pytest.mark.skipif(not _qt_available(), reason="PySide6 unavailable")
def test_gui_trail_spin_ranges_and_suffix(monkeypatch):
    import zeanalyser.analyse_gui_qt as gui_mod
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created = False
    app = gui_mod.QApplication.instance()
    if app is None:
        app = gui_mod.QApplication([])
        created = True
    win = gui_mod.ZeAnalyserMainWindow()
    try:
        # percentage range 0..100 (not 0..10000), suffix %
        assert win.trail_low_thr_spin.maximum() == pytest.approx(100.0)
        assert win.trail_high_thr_spin.maximum() == pytest.approx(100.0)
        assert win.trail_low_thr_spin.suffix().strip() == "%"
        assert win.trail_high_thr_spin.suffix().strip() == "%"
        # line_gap backend requires > 0
        assert win.trail_line_gap_spin.minimum() == 1

        # conversion 12.5% / 65% -> canonical .125 / .65
        win.trail_low_thr_spin.setValue(12.5)
        win.trail_high_thr_spin.setValue(65.0)
        opts = win._build_options_from_ui()
        assert opts["trail_params"]["low_thresh"] == pytest.approx(0.125)
        assert opts["trail_params"]["h_thresh"] == pytest.approx(0.65)
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created:
            app.quit()
