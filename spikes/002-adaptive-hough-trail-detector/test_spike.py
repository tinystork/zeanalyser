"""Local unit tests for the adaptive-Hough spike (TRAIL-02B).

Tests the spike's own plumbing only: preprocess/MAD noise, all-angle Hough
candidates, collinear grouping (incl. the 0/180 wrap), bounded trail matching,
feature validators (hard step + flat top), fail-safe schema, determinism/split,
fingerprints and CLI.  No detection threshold and no production code is asserted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import detector as det          # noqa: E402
import run_spike                # noqa: E402
import synthetic as syn         # noqa: E402
from synthetic import SPLITS    # noqa: E402
from metrics import (angular_distance_deg, assess_backend_case, assess_case,  # noqa: E402
                     match_trails, summarize)


# --------------------------------------------------------------------------- #
# Stage 1 — noise / MAD
# --------------------------------------------------------------------------- #
def test_preprocess_noise_mad_reasonable():
    rng = np.random.default_rng(1)
    img = rng.poisson(30, (128, 128)).astype(float) + rng.normal(0, 3, (128, 128))
    residual, noise = det.preprocess(img)
    assert residual.shape == (128, 128)
    assert 4.0 < noise < 15.0
    assert abs(np.median(residual)) < 3.0


def test_preprocess_noise_increases_with_noise():
    rng = np.random.default_rng(2)
    quiet = rng.poisson(30, (128, 128)).astype(float)
    loud = quiet + rng.normal(0, 10, (128, 128))
    _, n1 = det.preprocess(quiet)
    _, n2 = det.preprocess(loud)
    assert n2 > n1


# --------------------------------------------------------------------------- #
# Stage 2 — all-angle candidates
# --------------------------------------------------------------------------- #
def test_theta_covers_all_angles_including_axes():
    theta = np.deg2rad(np.arange(0.0, 180.0, det.CONFIG["theta_step_deg"]))
    assert theta[0] == 0.0
    assert np.isclose(np.radians(90.0), theta[int(90 / det.CONFIG["theta_step_deg"])])


def test_edge_segments_find_axis_trails():
    for cid in ("horiz_strong", "vert_strong"):
        img, gt = syn.build_case("dev", cid, 192)
        residual, noise = det.preprocess(img)
        segs = det.edge_segments(residual, noise, 192, 20261002)
        assert len(segs) > 0, cid
        phis = [det.line_params(p0, p1)[0] for (p0, p1) in segs]
        target = 0.0 if cid == "horiz_strong" else 90.0
        assert any(angular_distance_deg(p, target) < 3.0 for p in phis), (cid, phis)


# --------------------------------------------------------------------------- #
# Stage 3 — collinear grouping (incl. the 0/180 wrap)
# --------------------------------------------------------------------------- #
def test_group_into_lines_merges_collinear():
    segs = [((0, 0), (50, 0)), ((60, 0), (120, 0)), ((130, 0), (190, 0)),
            ((0, 2), (50, 2))]
    lines = det.group_into_lines(segs)
    assert len(lines) == 2


def test_group_into_trails_merges_parallel_edges():
    lines = [
        {"phi": 45.0, "rho": 1.0, "p0": (0, 0), "p1": (100, 100),
         "length": 141.4, "n_segments": 2},
        {"phi": 45.0, "rho": 4.0, "p0": (2, -2), "p1": (102, 98),
         "length": 141.4, "n_segments": 2},
    ]
    trails = det.group_into_trails(lines)
    assert len(trails) == 1
    assert trails[0]["n_lines"] == 2
    assert abs(trails[0]["rho"] - 2.5) < 1e-6


def test_group_into_trails_keeps_distinct_angles_separate():
    lines = [
        {"phi": 45.0, "rho": 1.0, "p0": (0, 0), "p1": (100, 100),
         "length": 141.4, "n_segments": 2},
        {"phi": 135.0, "rho": 130.0, "p0": (0, 100), "p1": (100, 0),
         "length": 141.4, "n_segments": 2},
    ]
    trails = det.group_into_trails(lines)
    assert len(trails) == 2


def test_rho_sign_consistency_reverse_line():
    p0, p1 = (10, 20), (30, 40)
    phi_a, theta_a, rho_a = det.line_params(p0, p1)
    phi_b, theta_b, rho_b = det.line_params(p1, p0)
    assert angular_distance_deg(phi_a, phi_b) < 1e-9
    assert abs(theta_a - theta_b) < 1e-9
    assert abs(rho_a - rho_b) < 1e-6


# --- fix 3: circular orientation mean --- #
def test_circular_mean_angle_wrap():
    assert det.circular_mean_angle([179.0, 1.0]) == pytest.approx(0.0, abs=1.0)
    assert det.circular_mean_angle([179.0, 0.0]) == pytest.approx(179.5, abs=1.0)
    assert det.circular_mean_angle([90.0, 90.0]) == pytest.approx(90.0, abs=0.01)
    assert det.circular_mean_angle([0.0, 180.0]) == pytest.approx(0.0, abs=0.01)


def test_group_lines_near_wrap_not_90():
    # one segment tilting up (phi~179), one tilting down (phi~1): same near-
    # horizontal line, must cluster to ~0 deg, not 90 deg.
    segs = [((0, 50), (100, 48)), ((0, 50), (100, 52))]
    lines = det.group_into_lines(segs)
    assert len(lines) == 1
    assert angular_distance_deg(lines[0]["phi"], 0.0) < 3.0


# --------------------------------------------------------------------------- #
# Stage 4/5 — feature validators
# --------------------------------------------------------------------------- #
def _synth_ridge(shape=(128, 128), flux=400.0, width=1.5, axis="diag"):
    img = np.zeros(shape, float)
    n = shape[0]
    if axis == "diag":
        p0, p1 = (8, 8), (n - 9, n - 9)
    elif axis == "v":
        p0, p1 = (n // 2, 4), (n // 2, n - 5)
    else:
        p0, p1 = (4, n // 2), (n - 5, n // 2)
    syn.draw_streak(img, p0, p1, flux, width)
    return img, p0, p1


def _trail_dict(p0, p1, n_lines=2, rho_spread=4.0):
    return {"phi": det.angle_from_endpoints(p0, p1), "rho": det.line_params(p0, p1)[2],
            "p0": p0, "p1": p1, "length": 200.0, "n_lines": n_lines,
            "n_segments": 2, "rho_spread": rho_spread}


def test_measure_validates_clean_ridge():
    img, p0, p1 = _synth_ridge()
    residual, noise = det.preprocess(img)
    out = det.measure_and_validate(residual, noise, _trail_dict(p0, p1), 128)
    assert out["accepted"] is True
    assert out["features"]["contrast_snr"] > 20
    assert out["features"]["continuity"] > 0.8
    assert 1.0 <= out["features"]["width_fwhm"] <= 9.0
    assert out["features"]["step_sharpness"] < det.CONFIG["max_step_sharpness"]
    assert out["features"]["tophat"] < det.CONFIG["max_tophat"]
    assert 0.0 <= out["score"] <= 1.0
    assert set(["contrast", "continuity", "width", "shape", "support"]) \
        <= set(out["component_scores"])


def test_measure_rejects_hard_column():
    img = np.zeros((128, 128), float)
    img[:, 60:62] += 120.0
    residual, noise = det.preprocess(img)
    trail = {"phi": 90.0, "rho": 61.0, "p0": (61, 4), "p1": (61, 124),
             "length": 120.0, "n_lines": 2, "n_segments": 2, "rho_spread": 2.0}
    out = det.measure_and_validate(residual, noise, trail, 128)
    assert out["features"]["step_sharpness"] > det.CONFIG["max_step_sharpness"]
    assert any("step_sharpness" in r for r in out["reasons"])
    assert out["accepted"] is False


def test_measure_rejects_soft_column():
    # 4-px plateau smoothed sigma=1 -> flat top (high tophat), low step_sharpness
    img = np.zeros((128, 128), float)
    img[:, 60:64] += 120.0
    from scipy import ndimage as _ndi
    img = _ndi.gaussian_filter(img, sigma=1.0)
    residual, noise = det.preprocess(img)
    trail = {"phi": 90.0, "rho": 62.0, "p0": (62, 4), "p1": (62, 124),
             "length": 120.0, "n_lines": 2, "n_segments": 2, "rho_spread": 4.0}
    out = det.measure_and_validate(residual, noise, trail, 128)
    assert out["features"]["step_sharpness"] < det.CONFIG["max_step_sharpness"]
    assert out["features"]["tophat"] > det.CONFIG["max_tophat"]
    assert any("tophat" in r for r in out["reasons"])
    assert out["accepted"] is False


def test_measure_rejects_discontinuous():
    img = np.zeros((128, 128), float)
    syn.add_stars(img, [(20, 64), (108, 64)], peak=400.0, psf_sigma=1.5)
    residual, noise = det.preprocess(img)
    trail = {"phi": 0.0, "rho": 64.0, "p0": (10, 64), "p1": (118, 64),
             "length": 108.0, "n_lines": 1, "n_segments": 1, "rho_spread": 0.0}
    out = det.measure_and_validate(residual, noise, trail, 128)
    assert out["features"]["continuity"] < det.CONFIG["min_continuity"]
    assert out["accepted"] is False


# --------------------------------------------------------------------------- #
# Fail-safe / schema
# --------------------------------------------------------------------------- #
def test_detect_returns_bounded_schema():
    img, gt = syn.build_case("dev", "diag_strong", 128)
    res = det.detect(img, 128, 20261002)
    assert res["state"] == "ok"
    for k in ("n_segments", "n_lines", "n_trails", "n_accepted", "segments",
              "lines", "trails", "noise"):
        assert k in res
    for s in res["segments"]:
        assert set(s.keys()) == {"p0", "p1"}
    for t in res["trails"]:
        assert "features" in t and "score" in t and "accepted" in t


def test_detect_failsafe_on_bad_input():
    res = det.detect(np.zeros((0, 0)), 128, 20261002)
    assert res["state"] == "error"
    assert res["n_accepted"] is None


# --------------------------------------------------------------------------- #
# Determinism / split
# --------------------------------------------------------------------------- #
def test_detect_deterministic():
    img, gt = syn.build_case("blind", "two_mixed", 192)
    r1 = det.detect(img, 192, syn.BLIND_SEED)
    r2 = det.detect(img, 192, syn.BLIND_SEED)
    assert r1["n_trails"] == r2["n_trails"]
    assert r1["n_accepted"] == r2["n_accepted"]


def test_three_splits_distinct_seeds():
    assert set(SPLITS.keys()) == {"dev", "observed_holdout", "blind"}
    seeds = {SPLITS[sk]["seed"] for sk in SPLITS}
    assert len(seeds) == 3
    assert syn.DEV_SEED != syn.OBSERVED_HOLDOUT_SEED != syn.BLIND_SEED
    assert set(syn.DEV_CASE_IDS) != set(syn.OBSERVED_HOLDOUT_CASE_IDS)
    assert set(syn.OBSERVED_HOLDOUT_CASE_IDS) != set(syn.BLIND_CASE_IDS)


def test_blind_cases_build_and_flags():
    for cid in syn.BLIND_CASE_IDS:
        img, gt = syn.build_case("blind", cid, 128)
        assert img.shape == (128, 128)
        assert gt["gt_has_trail"] == (cid in syn.BLIND_POSITIVES)
    # 8 positives / 9 negatives
    assert len(syn.BLIND_POSITIVES) == 8
    assert len(syn.BLIND_CASE_IDS) - len(syn.BLIND_POSITIVES) == 9


def test_generator_deterministic_blind():
    a1, _ = syn.build_case("blind", "weak_73", 192)
    a2, _ = syn.build_case("blind", "weak_73", 192)
    assert (a1 == a2).all()


# --------------------------------------------------------------------------- #
# Metrics — bounded matching (fix 2) + backend normalisation (fix 1)
# --------------------------------------------------------------------------- #
def test_match_trails_localization():
    gt = {"gt_trails": [{"label": "diag", "p0": (8, 8), "p1": (183, 183),
                          "angle_deg": 45.0}]}
    accepted = [{"phi": 44.5, "rho": 0.5, "p0": (9, 9), "p1": (182, 182),
                 "score": 0.9, "accepted": True}]
    matches, unmatched = match_trails(gt, accepted)
    assert len(matches) == 1 and matches[0]["matched"] is True
    assert matches[0]["angle_error_deg"] == pytest.approx(0.5, abs=0.1)
    assert matches[0]["offset_error_px"] < 2.0
    assert unmatched == []


def test_match_trails_rejects_wrong_angle():
    gt = {"gt_trails": [{"label": "diag", "p0": (8, 8), "p1": (183, 183),
                          "angle_deg": 45.0}]}
    accepted = [{"phi": 90.0, "rho": 0.0, "p0": (96, 0), "p1": (96, 191),
                 "score": 0.9, "accepted": True}]
    matches, unmatched = match_trails(gt, accepted)
    assert matches[0]["matched"] is False
    assert len(unmatched) == 1


def test_match_trails_rejects_wrong_rho():
    gt = {"gt_trails": [{"label": "diag", "p0": (8, 8), "p1": (183, 183),
                          "angle_deg": 45.0}]}
    accepted = [{"phi": 45.0, "rho": 100.0, "p0": (8, 8), "p1": (183, 183),
                 "score": 0.9, "accepted": True}]
    matches, unmatched = match_trails(gt, accepted)
    assert matches[0]["matched"] is False
    assert len(unmatched) == 1


def test_assess_case_grouping_coherent():
    # two GT trails, two matched accepted trails, no extra -> coherent
    gt = {"gt_has_trail": True,
          "gt_trails": [{"label": "a", "p0": (8, 8), "p1": (183, 183), "angle_deg": 45.0},
                        {"label": "b", "p0": (8, 183), "p1": (183, 8), "angle_deg": 135.0}]}
    res = {"state": "ok", "n_accepted": 2, "n_trails": 2,
           "trails": [{"phi": 45.0, "rho": 0.0, "p0": (8, 8), "p1": (183, 183),
                       "score": 0.9, "accepted": True},
                      {"phi": 135.0, "rho": 135.06, "p0": (8, 183), "p1": (183, 8),
                       "score": 0.8, "accepted": True}]}
    out = assess_case(gt, res)
    assert out["n_matched"] == 2
    assert out["n_missed"] == 0
    assert out["n_extra"] == 0
    assert out["grouping_coherent"] is True


def test_assess_backend_case_satdet_detected():
    gt = {"gt_has_trail": True, "gt_trails": [{"p0": (0, 0), "p1": (10, 10), "angle_deg": 45.0}]}
    res = {"state": "ok", "detected": True, "n_accepted": None, "n_segments": 2,
           "backend": "acstools.satdet"}
    out = assess_backend_case(gt, res)
    assert out["is_true_positive"] is True


def test_assess_backend_case_satdet_not_detected_is_fn():
    gt = {"gt_has_trail": True, "gt_trails": [{"p0": (0, 0), "p1": (10, 10), "angle_deg": 45.0}]}
    res = {"state": "ok", "detected": False, "n_accepted": None, "backend": "acstools.satdet"}
    out = assess_backend_case(gt, res)
    assert out["is_true_positive"] is False


def test_assess_backend_case_mrt_uses_detected():
    gt = {"gt_has_trail": False, "gt_trails": []}
    res = {"state": "ok", "detected": True, "n_accepted": 1, "backend": "acstools.findsat_mrt"}
    out = assess_backend_case(gt, res)
    assert out["is_false_positive"] is True


def test_assess_backend_case_non_ok_unevaluated():
    gt = {"gt_has_trail": True, "gt_trails": [{"p0": (0, 0), "p1": (10, 10), "angle_deg": 45.0}]}
    res = {"state": "error", "detected": False}
    out = assess_backend_case(gt, res)
    assert out["is_true_positive"] is None


def test_summarize_fp_by_class():
    rows = [
        {"case_id": "a", "state": "ok", "gt_has_trail": True,
         "is_true_positive": True, "is_false_positive": False, "runtime_s": 1.0},
        {"case_id": "b", "state": "ok", "gt_has_trail": False,
         "is_true_positive": False, "is_false_positive": True, "runtime_s": 2.0},
    ]
    s = summarize(rows)
    assert s["synthetic_tp"] == 1
    assert s["synthetic_fp"] == 1
    assert s["fp_by_class"] == ["b"]


# --------------------------------------------------------------------------- #
# Fingerprints (fix 5)
# --------------------------------------------------------------------------- #
def _minimal_payload():
    results = {}
    summary = {}
    for sk in SPLITS:
        cid = SPLITS[sk]["case_ids"][0]
        gt = {"gt_has_trail": True,
              "gt_trails": [{"label": "x", "p0": (8, 8), "p1": (183, 183), "angle_deg": 45.0}]}
        res = {"state": "ok", "n_accepted": 1, "n_trails": 1,
               "trails": [{"phi": 45.0, "rho": 0.0, "p0": (8, 8), "p1": (183, 183),
                           "score": 0.9, "accepted": True, "features": {}, "reasons": []}],
               "runtime_s": 1.0, "case_id": cid, "split": sk}
        row = assess_case(gt, res)
        results[sk] = [row]
        summary[sk] = summarize([row])
    meta = {"mission": "test", "size": 192, "config": det.CONFIG,
            "rss_method": "test", "rss_baselines_kb": {sk: 1 for sk in SPLITS},
            "generated_at_utc": "test", "fingerprints": run_spike._fingerprints()}
    for sk in SPLITS:
        meta[f"seed_{sk}"] = SPLITS[sk]["seed"]
        meta[f"{sk}_case_ids"] = [SPLITS[sk]["case_ids"][0]]
    return {"meta": meta, "results": results, "summary": summary}


def test_fingerprints_include_001_files():
    fps = run_spike._fingerprints()
    assert "../001-trail-detector-comparison/synthetic.py" in fps
    assert "../001-trail-detector-comparison/adapters.py" in fps


def test_check_results_valid(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_minimal_payload()))
    code, msg = run_spike.check_results(str(p))
    assert code == 0, msg


def test_check_results_fingerprint_change_fails(tmp_path):
    payload = _minimal_payload()
    payload["meta"]["fingerprints"]["../001-trail-detector-comparison/synthetic.py"] = "0" * 64
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


# --------------------------------------------------------------------------- #
# CLI smoke
# --------------------------------------------------------------------------- #
def test_runner_help_and_quick_smoke(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_spike.py"),
                        "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "usage" in r.stdout.lower()

    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "run_spike.py"), "--quick",
         "--case", "diag_strong", "--out-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    data = json.load(open(str(tmp_path / "results_run.json")))
    assert data["meta"]["size"] == 192
    assert len(data["results"]["dev"]) == 1
    assert data["summary"]["dev"]["synthetic_tp"] == 1


# --------------------------------------------------------------------------- #
# Rework-2 regression tests
# --------------------------------------------------------------------------- #
# fix 1: image TP is geometrically matched
# --------------------------------------------------------------------------- #
def test_assess_case_positive_unmatched_is_fn():
    gt = {"gt_has_trail": True,
          "gt_trails": [{"label": "d", "p0": (8, 8), "p1": (183, 183), "angle_deg": 45.0}]}
    # accepted trail at the wrong angle (phi 90) -> not matched -> FN image, not TP
    res = {"state": "ok", "n_accepted": 1, "n_trails": 1,
           "trails": [{"phi": 90.0, "rho": 0.0, "p0": (96, 0), "p1": (96, 191),
                       "score": 0.9, "accepted": True}]}
    out = assess_case(gt, res)
    assert out["is_true_positive"] is False
    assert out["is_false_positive"] is False
    assert out["n_matched"] == 0
    assert out["n_missed"] == 1
    assert out["n_extra"] == 1


def test_assess_case_multi_partial_match_is_tp_but_not_coherent():
    gt = {"gt_has_trail": True,
          "gt_trails": [{"label": "a", "p0": (8, 8), "p1": (183, 183), "angle_deg": 45.0},
                        {"label": "b", "p0": (8, 183), "p1": (183, 8), "angle_deg": 135.0}]}
    # only trail a matched (1 accepted trail) -> image TP, but grouping false
    res = {"state": "ok", "n_accepted": 1, "n_trails": 1,
           "trails": [{"phi": 45.0, "rho": 0.0, "p0": (8, 8), "p1": (183, 183),
                       "score": 0.9, "accepted": True}]}
    out = assess_case(gt, res)
    assert out["is_true_positive"] is True
    assert out["n_matched"] == 1
    assert out["n_missed"] == 1
    assert out["physical_trail_rate"] == 0.5
    assert out["grouping_coherent"] is False


# --------------------------------------------------------------------------- #
# fix 2: bounded (complete-link) grouping, no transitive chain bridging
# --------------------------------------------------------------------------- #
def test_group_lines_no_chain_bridging():
    # rho 0 / 1 / 2 with tol 1: 0-1 and 1-2 are within tol but 0-2 = 2 > 1.
    # single-link would merge all three (spread 2 > tol); complete-link must not.
    segs = [((0, 0), (100, 0)), ((0, 1), (100, 1)), ((0, 2), (100, 2))]
    lines = det.group_into_lines(segs)
    assert len(lines) == 2


def test_group_trails_no_rho_chain_bridging():
    # 3 parallel lines at rho 0 / 7 / 14 (full overlap), max_width 8.
    # single-link would bridge 0-7-14 (spread 14 > 8); complete-link must not.
    lines = [
        {"phi": 45.0, "rho": 0.0, "p0": (0, 0), "p1": (100, 100),
         "length": 141.4, "n_segments": 2},
        {"phi": 45.0, "rho": 7.0, "p0": (0, 0), "p1": (100, 100),
         "length": 141.4, "n_segments": 2},
        {"phi": 45.0, "rho": 14.0, "p0": (0, 0), "p1": (100, 100),
         "length": 141.4, "n_segments": 2},
    ]
    trails = det.group_into_trails(lines)
    assert len(trails) == 2
    for t in trails:
        assert t["rho_spread"] <= det.CONFIG["trail_max_width"]


# --------------------------------------------------------------------------- #
# fix 3: checker validates the saved 001 comparison
# --------------------------------------------------------------------------- #
def _build_comparison():
    rows = []
    for cid in SPLITS["observed_holdout"]["case_ids"]:
        pos = cid in SPLITS["observed_holdout"]["positives"]
        gt = {"gt_has_trail": pos,
              "gt_trails": ([{"label": "x", "p0": (8, 8), "p1": (183, 183), "angle_deg": 45.0}]
                            if pos else [])}
        for b in ("acstools.satdet", "acstools.findsat_mrt"):
            res = {"state": "ok", "detected": False, "n_accepted": 0, "backend": b,
                   "runtime_s": 0.1, "case_id": cid, "split": "observed_holdout"}
            rows.append(assess_backend_case(gt, res))
    sat = summarize([r for r in rows if r["backend"] == "acstools.satdet"])
    mrt = summarize([r for r in rows if r["backend"] == "acstools.findsat_mrt"])
    return {"satdet": sat, "mrt": mrt, "rows": rows}


def _payload_with_comparison():
    payload = _minimal_payload()
    payload["comparison"] = _build_comparison()
    return payload


def test_check_results_comparison_valid(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_payload_with_comparison()))
    code, msg = run_spike.check_results(str(p))
    assert code == 0, msg
    assert "comparison OK" in msg


def test_check_results_comparison_altered_summary_fails(tmp_path):
    payload = _payload_with_comparison()
    payload["comparison"]["satdet"]["synthetic_tp"] = 999
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_comparison_duplicate_row_fails(tmp_path):
    payload = _payload_with_comparison()
    payload["comparison"]["rows"].append(dict(payload["comparison"]["rows"][0]))
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_comparison_missing_row_fails(tmp_path):
    payload = _payload_with_comparison()
    payload["comparison"]["rows"] = payload["comparison"]["rows"][:-1]
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_no_comparison_accepted(tmp_path):
    payload = _minimal_payload()  # no comparison key
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code == 0, msg
    assert "comparison absent" in msg
