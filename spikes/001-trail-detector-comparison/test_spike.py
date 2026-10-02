"""Local smoke tests for the satdet-vs-MRT spike (TRAIL-02A).

These tests validate the spike's own plumbing only: the synthetic generator is
deterministic, the adapters return the common schema, and the metrics helpers
behave.  They do **not** assert any detection threshold and do **not** touch
production code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_comparison       # noqa: E402
import synthetic            # noqa: E402
from adapters import run_mrt, run_satdet  # noqa: E402
from metrics import angular_distance_deg, assess_case, summarize  # noqa: E402


def test_generator_deterministic():
    a1, _ = synthetic.build_case("diag_strong", 192, 20261002)
    a2, _ = synthetic.build_case("diag_strong", 192, 20261002)
    assert a1.shape == (192, 192)
    assert (a1 == a2).all()


def test_generator_ground_truth_shapes():
    for cid in synthetic.CASE_IDS:
        img, gt = synthetic.build_case(cid, 128, 1)
        assert img.shape == (128, 128)
        assert set(["case_id", "gt_has_trail", "gt_trails"]) <= set(gt)
        assert isinstance(gt["gt_has_trail"], bool)


def test_angle_convention():
    assert angular_distance_deg(0.0, 0.0) == 0.0
    assert angular_distance_deg(0.0, 180.0) == 0.0
    assert angular_distance_deg(0.0, 90.0) == 90.0
    assert angular_distance_deg(179.0, 1.0) == 2.0


def test_satdet_adapter_returns_schema():
    img, gt = synthetic.build_case("diag_strong", 128, 2)
    res = run_satdet(img, 128, 2)
    for key in ("backend", "version", "state", "runtime_s", "n_segments",
                "detected", "error"):
        assert key in res
    assert res["backend"] == "acstools.satdet"


def test_mrt_adapter_returns_schema():
    img, gt = synthetic.build_case("diag_strong", 128, 2)
    res = run_mrt(img, 128, 1.0, 2)
    for key in ("backend", "version", "state", "runtime_s", "n_sources",
                "n_accepted", "n_candidate", "status_counts", "detected",
                "error"):
        assert key in res
    assert res["backend"] == "acstools.findsat_mrt"
    if res["n_sources"] is not None:
        assert res["status_counts"] is not None


def test_assess_case_positive_detected():
    gt = {"gt_has_trail": True,
          "gt_trails": [{"angle_deg": 45.0, "p0": (0, 0), "p1": (10, 10)}]}
    res = {"detected": True, "angles_deg": [44.0], "runtime_s": 0.1,
           "state": "ok"}
    out = assess_case(gt, res)
    assert out["is_true_positive"] is True
    assert out["is_false_positive"] is False
    assert out["angle_error_deg"] == pytest.approx(1.0)


def test_assess_case_negative_false_positive():
    gt = {"gt_has_trail": False, "gt_trails": []}
    res = {"detected": True, "angles_deg": [45.0], "runtime_s": 0.1,
           "state": "ok"}
    out = assess_case(gt, res)
    assert out["is_false_positive"] is True
    assert out["is_true_positive"] is False
    assert out["angle_error_deg"] is None


def test_summarize_counts():
    rows = [
        {"gt_has_trail": True, "is_true_positive": True,
         "is_false_positive": False, "runtime_s": 1.0, "state": "ok"},
        {"gt_has_trail": True, "is_true_positive": False,
         "is_false_positive": False, "runtime_s": 2.0, "state": "ok"},
        {"gt_has_trail": False, "is_true_positive": False,
         "is_false_positive": True, "runtime_s": 3.0, "state": "ok"},
    ]
    s = summarize(rows)
    assert s["synthetic_tp"] == 1
    assert s["synthetic_fp"] == 1
    assert s["synthetic_fn"] == 1
    assert s["synthetic_tn"] == 0
    assert s["synthetic_detection_rate_positives"] == 0.5
    assert s["runtime_s_p50"] == 2.0


def test_runner_help_and_quick_smoke():
    """--help exits 0; a minimal quick run produces valid JSON with metadata."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_comparison.py"),
                        "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "usage" in r.stdout.lower()

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "run_comparison.py"),
             "--quick", "--case", "diag_strong", "--out-dir", td],
            capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-2000:]
        data = json.load(open(os.path.join(td, "results_run.json")))
        meta = data["meta"]
        assert meta["seed"] == 20261002
        assert meta["size"] == 192
        assert len(data["results"]) == 2  # satdet + mrt
        # every result carries backend + version
        for row in data["results"]:
            assert row["backend"]
            assert row["version"]


# --------------------------------------------------------------------------- #
# Rework-1 regression tests
# --------------------------------------------------------------------------- #
def _redirect_tempdir(monkeypatch, tmp_path):
    """Force tempfile (mkdtemp / TemporaryDirectory) under ``tmp_path``."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return set(os.listdir(tmp_path))


def test_no_temp_residue_adapters_success(tmp_path, monkeypatch):
    before = _redirect_tempdir(monkeypatch, tmp_path)
    img, gt = synthetic.build_case("diag_strong", 128, 3)
    run_satdet(img, 128, 3)
    run_mrt(img, 128, 1.0, 3)
    assert set(os.listdir(tmp_path)) == before  # nothing residual


def test_mrt_exception_leaves_no_temp(tmp_path, monkeypatch):
    before = _redirect_tempdir(monkeypatch, tmp_path)
    # 1-D input -> radon raises ValueError *inside* the TemporaryDirectory block.
    res = run_mrt(np.zeros((64,)), 128, 1.0, 3)
    assert res["state"] == "error"
    assert set(os.listdir(tmp_path)) == before


def test_satdet_exception_leaves_no_temp(tmp_path, monkeypatch):
    before = _redirect_tempdir(monkeypatch, tmp_path)
    # Empty image -> percentile/rescale path raises inside the mkdtemp try block.
    res = run_satdet(np.zeros((0, 0)), 128, 3)
    assert res["state"] == "error"
    assert set(os.listdir(tmp_path)) == before


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_subprocess_timeout(monkeypatch):
    def _raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(run_comparison.subprocess, "run", _raise_timeout)
    res = run_comparison._run_subprocess(["--worker"], timeout=1)
    assert res["state"] == "timeout"
    assert "timed out" in res["error"]


def test_run_subprocess_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(1, stdout='{"state": "ok", "detected": true}'))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert res["detected"] is False


def test_run_subprocess_invalid_json(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(0, stdout="this is not json"))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert "valid JSON" in res["error"]


def test_assess_case_non_ok_is_none():
    gt = {"gt_has_trail": True,
          "gt_trails": [{"angle_deg": 45.0, "p0": (0, 0), "p1": (10, 10)}]}
    res = {"state": "timeout", "detected": False, "runtime_s": None,
           "error": "x"}
    out = assess_case(gt, res)
    assert out["is_true_positive"] is None
    assert out["is_false_positive"] is None
    assert out["angle_error_deg"] is None


def test_summarize_technical_failure_not_false_negative():
    rows = [
        {"gt_has_trail": True, "state": "ok", "is_true_positive": True,
         "is_false_positive": False, "runtime_s": 1.0},
        {"gt_has_trail": True, "state": "error", "is_true_positive": None,
         "is_false_positive": None, "runtime_s": None},
        {"gt_has_trail": False, "state": "timeout", "is_true_positive": None,
         "is_false_positive": None, "runtime_s": None},
    ]
    s = summarize(rows)
    assert s["n_ok"] == 1
    assert s["n_error"] == 1
    assert s["n_timeout"] == 1
    assert s["n_unevaluated_positive"] == 1
    assert s["n_unevaluated_negative"] == 1
    assert s["synthetic_tp"] == 1
    assert s["synthetic_fn"] == 0  # error row NOT counted as FN
    assert s["synthetic_fp"] == 0  # timeout row NOT counted as FP
    assert s["synthetic_detection_rate_positives"] == 1.0


# --------------------------------------------------------------------------- #
# Rework-2 regression tests
# --------------------------------------------------------------------------- #
def test_run_subprocess_non_object_json_list(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(0, stdout="[]"))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert res["detected"] is False
    assert res["runtime_s"] is None
    assert "must be an object" in res["error"]


def test_run_subprocess_non_object_json_null(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(0, stdout="null"))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert "must be an object" in res["error"]


def test_run_subprocess_non_object_json_scalar(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(0, stdout='"a string"'))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert "must be an object" in res["error"]


def test_run_subprocess_nonzero_with_null_error(monkeypatch):
    monkeypatch.setattr(
        run_comparison.subprocess, "run",
        lambda *a, **k: _FakeProc(
            1, stdout='{"state": "ok", "detected": true, "error": null}'))
    res = run_comparison._run_subprocess(["--worker"])
    assert res["state"] == "error"
    assert res["detected"] is False
    assert res["runtime_s"] is None
    assert isinstance(res["error"], str) and res["error"]  # not None/empty


def test_run_all_unknown_case_raises(tmp_path):
    with pytest.raises(ValueError) as exc:
        run_comparison.run_all(192, 1.0, 20261002, str(tmp_path),
                               only_cases=["not_a_case"])
    assert "Unknown case id" in str(exc.value)


def test_cli_invalid_case_exit_nonzero():
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "run_comparison.py"),
         "--case", "not_a_case"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert "invalid choice" in r.stderr.lower()


# --------------------------------------------------------------------------- #
# Rework-3 regression tests: --check-results mechanical validation
# --------------------------------------------------------------------------- #
def _build_results_payload(case_ids=("diag_strong",)):
    """Build a minimal but schema-valid results payload (no subprocess)."""
    from adapters import BACKENDS
    rows = []
    for cid in case_ids:
        gt = {"gt_has_trail": True,
              "gt_trails": [{"angle_deg": 45.0, "p0": (0, 0),
                              "p1": (10, 10)}]}
        for bmeta in BACKENDS.values():
            row = {"backend": bmeta["label"], "version": "3.8.2",
                   "state": "ok", "runtime_s": 1.0, "detected": True,
                   "angles_deg": [45.0], "case_id": cid}
            rows.append(assess_case(gt, row))
    summary = {}
    for bmeta in BACKENDS.values():
        summary[bmeta["label"]] = summarize(
            [r for r in rows if r["backend"] == bmeta["label"]])
    meta = {"mission": "test", "size": 192, "theta_step": 1.0, "seed": 1,
            "rss_method": "test", "rss_baselines_kb": {"satdet": 1, "mrt": 1},
            "case_ids": list(case_ids), "generated_at_utc": "test",
            "fingerprints": run_comparison._fingerprints()}
    return {"meta": meta, "results": rows, "summary": summary}


def test_check_results_valid(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_build_results_payload()))
    code, msg = run_comparison.check_results(str(p))
    assert code == 0, msg


def test_check_results_altered_summary_fails(tmp_path):
    payload = _build_results_payload()
    payload["summary"]["acstools.satdet"]["synthetic_tp"] = 999
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_comparison.check_results(str(p))
    assert code != 0


def test_check_results_altered_fingerprint_fails(tmp_path):
    payload = _build_results_payload()
    payload["meta"]["fingerprints"]["synthetic.py"] = "0" * 64
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_comparison.check_results(str(p))
    assert code != 0


def test_check_results_duplicate_pair_fails(tmp_path):
    payload = _build_results_payload()
    payload["results"].append(dict(payload["results"][0]))  # duplicate
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_comparison.check_results(str(p))
    assert code != 0


def test_check_results_missing_pair_fails(tmp_path):
    payload = _build_results_payload(case_ids=("diag_strong", "horiz_strong"))
    payload["results"] = [
        r for r in payload["results"]
        if not (r["case_id"] == "horiz_strong"
                and r["backend"] == "acstools.findsat_mrt")]
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_comparison.check_results(str(p))
    assert code != 0


@pytest.mark.parametrize("bad_case_ids", [[[]], [{"bad": "shape"}]])
def test_check_results_malformed_case_ids_never_raise(tmp_path, bad_case_ids):
    payload = _build_results_payload()
    payload["meta"]["case_ids"] = bad_case_ids
    p = tmp_path / "malformed.json"
    p.write_text(json.dumps(payload))

    code, message = run_comparison.check_results(str(p))

    assert code != 0
    assert "failed validation" in message
