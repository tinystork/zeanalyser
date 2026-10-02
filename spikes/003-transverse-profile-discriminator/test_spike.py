"""Local unit tests for the transverse-profile discriminator spike (TRAIL-02C).

Tests the spike's own plumbing only: sub-pixel sampling (invariant to offsets,
no rounding), ridge/plateau model fits, the three-way ambiguity decision,
fail-safe non-convergence, determinism, absence of blind-tuning metadata,
integration normalisation, and checker corruption detection.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import profile_models as pm            # noqa: E402
import run_spike                        # noqa: E402
import synthetic_profiles as sp         # noqa: E402
from profile_models import CONFIG, default_offsets, discriminate_profile  # noqa: E402
from synthetic_profiles import (  # noqa: E402
    SPLITS, build_case, sample_profile_from_image)


# --------------------------------------------------------------------------- #
# Sub-pixel sampling
# --------------------------------------------------------------------------- #
def _analytic_gauss(offsets, center, sigma, amp):
    return amp * np.exp(-0.5 * ((offsets - center) / sigma) ** 2)


def test_sample_subpixel_recovers_gaussian_ridge():
    n = 192
    img = np.zeros((n, n), float)
    p0, p1 = (16, 96), (176, 96)     # horizontal ridge at y=96
    sigma, amp = 1.5, 400.0
    sp.draw_ridge(img, p0, p1, amp, sigma)
    offsets = default_offsets()
    prof, cov = pm.sample_transverse_profile_subpixel(img, p0, p1, offsets)
    assert cov > 0.9
    # fit a ridge to the sampled profile: sigma must be recovered (~1.5)
    dec = discriminate_profile(prof, offsets)
    assert dec["label"] == "ridge"
    assert dec["ridge"]["params"]["sigma"] == pytest.approx(sigma, abs=0.15)


def test_sample_subpixel_no_rounding_half_pixel_center():
    # A vertical ridge centred at x=96.5 (half-pixel) must sample cleanly
    # (bilinear, not round-to-nearest which would shift the peak to 96 or 97).
    n = 192
    img = np.zeros((n, n), float)
    p0, p1 = (96.5, 16), (96.5, 176)
    sp.draw_ridge(img, p0, p1, 400.0, 1.2)
    offsets = default_offsets()
    prof, cov = pm.sample_transverse_profile_subpixel(img, p0, p1, offsets)
    assert cov > 0.9
    dec = discriminate_profile(prof, offsets)
    assert dec["label"] == "ridge"
    # centre must be recovered near 0 (profile-centred), sigma near 1.2
    assert abs(dec["ridge"]["params"]["center"]) < 0.2
    assert dec["ridge"]["params"]["sigma"] == pytest.approx(1.2, abs=0.15)


def test_sample_offset_invariance():
    # The discriminator must be invariant to where the feature sits on the grid.
    n = 192
    offsets = default_offsets()
    sigmas = []
    for cy in (96.0, 96.25, 96.5, 96.75):
        img = np.zeros((n, n), float)
        p0, p1 = (16, cy), (176, cy)
        sp.draw_ridge(img, p0, p1, 400.0, 1.5)
        prof, _ = pm.sample_transverse_profile_subpixel(img, p0, p1, offsets)
        dec = discriminate_profile(prof, offsets)
        sigmas.append(dec["ridge"]["params"]["sigma"])
    # all four sub-pixel positions recover the same sigma (<= 0.05 spread)
    assert max(sigmas) - min(sigmas) < 0.05


# --------------------------------------------------------------------------- #
# Model fits on direct profiles
# --------------------------------------------------------------------------- #
def test_ridge_fit_on_clean_gaussian():
    offsets = default_offsets()
    y = _analytic_gauss(offsets, 0.0, 1.5, 100.0) + np.random.default_rng(0).normal(0, 1.0, len(offsets))
    dec = discriminate_profile(y, offsets, noise=1.0)
    assert dec["label"] == "ridge"
    assert dec["ridge"]["params"]["sigma"] == pytest.approx(1.5, abs=0.15)
    assert dec["preference"] > 0


def test_column_fit_on_hard_plateau():
    offsets = default_offsets()
    y = np.where(np.abs(offsets) <= 2.0, 100.0, 0.0) + \
        np.random.default_rng(1).normal(0, 1.0, len(offsets))
    dec = discriminate_profile(y, offsets, noise=1.0)
    assert dec["label"] == "column"
    assert dec["column"]["params"]["width"] == pytest.approx(4.0, abs=0.6)
    assert dec["preference"] < 0


def test_soft_column_labeled_column_when_flat_top_resolvable():
    offsets = default_offsets()
    # hard band blurred by 0.5 -> softness < width/2 -> still "column"
    y = np.where(np.abs(offsets) <= 2.0, 100.0, 0.0)
    y = ndi.gaussian_filter1d(y, 0.5) + np.random.default_rng(2).normal(0, 1.0, len(offsets))
    dec = discriminate_profile(y, offsets, noise=1.0)
    assert dec["label"] == "column"


# --------------------------------------------------------------------------- #
# Ambiguity / fail-safe
# --------------------------------------------------------------------------- #
def test_no_structure_is_ambiguous():
    offsets = default_offsets()
    y = np.random.default_rng(3).normal(0, 1.0, len(offsets))
    dec = discriminate_profile(y, offsets, noise=1.0)
    assert dec["label"] == "ambiguous"


def test_double_ridge_is_ambiguous():
    offsets = default_offsets()
    y = (_analytic_gauss(offsets, -1.5, 0.8, 100.0)
         + _analytic_gauss(offsets, +1.5, 0.8, 100.0)
         + np.random.default_rng(4).normal(0, 1.0, len(offsets)))
    dec = discriminate_profile(y, offsets, noise=1.0)
    assert dec["label"] == "ambiguous"


def test_nonconvergence_is_ambiguous_never_accept():
    # a NaN profile must fail-safe to ambiguous (never a default accept)
    y = np.full(20, np.nan)
    dec = discriminate_profile(y, offsets=np.arange(20), noise=1.0)
    assert dec["label"] == "ambiguous"
    assert dec["converged"] is False


def test_flat_profile_is_ambiguous():
    y = np.ones(20) * 5.0
    dec = discriminate_profile(y, offsets=np.arange(20), noise=1.0)
    assert dec["label"] == "ambiguous"


def test_deterministic():
    offsets = default_offsets()
    rng = np.random.default_rng(5)
    y = _analytic_gauss(offsets, 0.2, 1.0, 80.0) + rng.normal(0, 2.0, len(offsets))
    d1 = discriminate_profile(y, offsets)
    d2 = discriminate_profile(y, offsets)
    assert d1["label"] == d2["label"]
    assert d1["preference"] == pytest.approx(d2["preference"], abs=1e-12)


# --------------------------------------------------------------------------- #
# Splits / generator determinism
# --------------------------------------------------------------------------- #
def test_two_splits_distinct_seeds():
    assert set(SPLITS.keys()) == {"dev", "blind"}
    assert sp.DEV_SEED != sp.BLIND_SEED
    assert set(SPLITS["dev"]["cases"]) != set(SPLITS["blind"]["cases"])


def test_blind_labels_preassigned_consistent():
    # blind labels must be pre-assigned and match the documented physical rule
    for cid, (img, p0, p1, gt) in SPLITS["blind"]["cases"].items():
        if gt["kind"] == "column":
            w, s = gt["width"], gt["softness"]
            expected = "column" if (s == 0 or w > 2 * s) else "ambiguous"
            assert gt["label"] == expected, cid


def test_build_case_deterministic():
    img1, p0, p1, gt1 = build_case("blind", "ridge_s0.7_c0.125")
    img2, _, _, gt2 = build_case("blind", "ridge_s0.7_c0.125")
    assert (img1 == img2).all()
    assert gt1 == gt2


# --------------------------------------------------------------------------- #
# Config freeze / no blind tuning metadata
# --------------------------------------------------------------------------- #
def test_config_hash_stable():
    assert run_spike._config_sha() == run_spike._config_sha()


def test_no_blind_tuning_metadata_in_payload(tmp_path):
    # build a minimal payload and confirm the checker rejects config drift
    payload = _minimal_payload()
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code == 0

    # tamper with frozen config -> must fail
    tampered = json.loads(p.read_text())
    tampered["meta"]["config"] = dict(CONFIG, pref_delta_threshold=0.99)
    p.write_text(json.dumps(tampered))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def _minimal_payload():
    results, summary = {}, {}
    for sk in SPLITS:
        rows = []
        for cid, (img, p0, p1, gt) in SPLITS[sk]["cases"].items():
            prof, noise, cov = sample_profile_from_image(img, p0, p1, default_offsets())
            dec = discriminate_profile(prof, default_offsets(), noise=noise)
            dec["runtime_s"] = 0.0
            dec["coverage"] = 1.0
            dec["noise"] = noise
            rows.append(run_spike.assess_profile(cid, gt, dec))
        results[sk] = rows
        summary[sk] = run_spike._confusion_summary(rows)
    return {
        "meta": {
            "mission": "test", "seed_dev": sp.DEV_SEED, "seed_blind": sp.BLIND_SEED,
            "config": CONFIG, "config_sha256": run_spike._config_sha(),
            "fingerprints": run_spike._fingerprints(),
            "generated_at_utc": "test",
        },
        "results": results, "summary": summary,
    }


def test_check_results_corruption_fails(tmp_path):
    payload = _minimal_payload()
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code == 0, msg

    # corrupt a summary -> fail
    payload["summary"]["dev"]["ridge_recall"] = 9.99
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_fingerprint_change_fails(tmp_path):
    payload = _minimal_payload()
    # corrupt a fingerprint
    first_key = next(iter(payload["meta"]["fingerprints"]))
    payload["meta"]["fingerprints"][first_key] = "0" * 64
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


# --------------------------------------------------------------------------- #
# Rework-1 — probe fail-closed shape gate
# --------------------------------------------------------------------------- #
def _force_shape(monkeypatch, label):
    import run_probe_impl

    def fake_shape(residual, trail, noise):
        return label, {"label": label, "preference": 0.0, "snr": 50.0,
                        "converged": True}, 1.0
    monkeypatch.setattr(run_probe_impl, "_probe_shape_decision", fake_shape)
    return run_probe_impl


def test_probe_shape_ridge_accepted(monkeypatch):
    rpi = _force_shape(monkeypatch, "ridge")
    img, gt = rpi._syn.build_case("dev", "diag_strong", 192)
    res = rpi.probe_detect(img, 192, rpi._syn.DEV_SEED)
    assert res["state"] == "ok"
    assert res["n_trails"] >= 1
    assert res["n_accepted"] >= 1
    for t in res["trails"]:
        if t["accepted"]:
            assert all("shape=" not in r for r in t["reasons"])


def test_probe_shape_column_rejected(monkeypatch):
    rpi = _force_shape(monkeypatch, "column")
    img, gt = rpi._syn.build_case("dev", "diag_strong", 192)
    res = rpi.probe_detect(img, 192, rpi._syn.DEV_SEED)
    assert res["state"] == "ok"
    assert res["n_trails"] >= 1
    assert res["n_accepted"] == 0
    for t in res["trails"]:
        assert any("shape=column" in r for r in t["reasons"])


def test_probe_shape_ambiguous_deferred_not_accepted(monkeypatch):
    # fail-closed: ambiguous must NOT be accepted by default.
    rpi = _force_shape(monkeypatch, "ambiguous")
    img, gt = rpi._syn.build_case("dev", "diag_strong", 192)
    res = rpi.probe_detect(img, 192, rpi._syn.DEV_SEED)
    assert res["state"] == "ok"
    assert res["n_trails"] >= 1
    assert res["n_accepted"] == 0
    for t in res["trails"]:
        assert any("shape=ambiguous" in r for r in t["reasons"])
        assert t["accepted"] is False


def test_probe_detect_failsafe_on_exception(monkeypatch):
    import run_probe_impl

    def boom(image, size, seed):
        raise RuntimeError("boom")
    monkeypatch.setattr(run_probe_impl, "_probe_detect", boom)
    res = run_probe_impl.probe_detect(np.zeros((64, 64)), 64, 1)
    assert res["state"] == "error"
    assert res["n_accepted"] is None
    assert res["trails"] == []


# --------------------------------------------------------------------------- #
# Rework-1 — noise consistency (runner + probe pass image/residual MAD)
# --------------------------------------------------------------------------- #
def test_probe_shape_decision_passes_noise(monkeypatch):
    import run_probe_impl
    captured = {}

    def fake_discriminate(profile, offsets=None, noise=None, cfg=None):
        captured["noise"] = noise
        return {"label": "ridge", "preference": 0.0, "snr": 50.0,
                "converged": True}
    monkeypatch.setattr(run_probe_impl, "discriminate_profile", fake_discriminate)
    residual = np.zeros((64, 64))
    trail = {"p0": (8, 32), "p1": (56, 32)}
    run_probe_impl._probe_shape_decision(residual, trail, noise=7.5)
    assert captured["noise"] == 7.5


def test_run_profile_passes_image_noise(monkeypatch):
    captured = {}

    def fake_discriminate(profile, offsets=None, noise=None, cfg=None):
        captured["noise"] = noise
        return {"label": "ridge", "preference": 0.0, "snr": 50.0,
                "converged": True}

    def fake_sample(image, p0, p1, offsets=None, n_long=None):
        return np.zeros(len(offsets)), 3.5, 1.0

    monkeypatch.setattr(run_spike, "discriminate_profile", fake_discriminate)
    monkeypatch.setattr(run_spike, "sample_profile_from_image", fake_sample)
    run_spike.run_profile("dev", "/tmp/whatever")
    assert captured["noise"] == pytest.approx(3.5)


def test_sample_profile_returns_finite_positive_noise():
    img, p0, p1, gt = build_case("blind", "ridge_s0.7_c0.125")
    prof, noise, cov = sample_profile_from_image(img, p0, p1, default_offsets())
    assert np.isfinite(noise) and noise > 0
    assert np.isfinite(prof).all()


# --------------------------------------------------------------------------- #
# Rework-1 — realistic synthetic (mask-only smoothing, signed asymmetry)
# --------------------------------------------------------------------------- #
def test_draw_column_smooths_mask_only_not_background():
    n = 64
    seed = 123
    img = sp.make_background((n, n), seed)
    p0, p1 = (32, 8), (32, n - 8)
    img_col = img.copy()
    sp.draw_column(img_col, p0, p1, width=4, amplitude=100.0, softness=1.0)
    # far from the band, pixels must be identical to the unsmoothed background
    far = np.abs(np.arange(n) - 32.0) > 10
    assert np.array_equal(img_col[:, far], img[:, far])
    # near the band, the defect must be present
    near = np.abs(np.arange(n) - 32.0) <= 2
    assert (img_col[:, near] > img[:, near]).any()


def test_asymmetric_case_is_not_symmetric():
    img, p0, p1, gt = sp._asymmetric_case(192, 20261006, 300.0, 3.0)
    assert gt["kind"] == "asymmetric"
    prof, noise, cov = sample_profile_from_image(img, p0, p1, default_offsets())
    n = len(prof)
    half = n // 2
    left = prof[:half]
    right = prof[n - half:][::-1]
    assert not np.allclose(left, right, atol=1.0)


# --------------------------------------------------------------------------- #
# Rework-1 — checker probe mode
# --------------------------------------------------------------------------- #
def _minimal_probe_payload(size=192):
    import run_probe_impl
    met = run_probe_impl._met
    datasets = {
        run_probe_impl.DATASET_002_BLIND: list(run_probe_impl._syn.BLIND_CASE_IDS),
        run_probe_impl.DATASET_AUDIT003: list(run_probe_impl._build_audit(size).keys()),
    }

    def make_rows(backend):
        rows = []
        for ds, ids in datasets.items():
            for cid in ids:
                rows.append({
                    "case_id": cid, "dataset": ds, "backend": backend,
                    "state": "ok", "gt_has_trail": False,
                    "is_true_positive": False, "is_false_positive": False,
                    "runtime_s": 1.0, "n_matched": 0, "gt_ntrails": 0,
                    "n_extra": 0, "grouping_coherent": None,
                    "angle_error_deg": None,
                })
        return rows

    baseline_rows = make_rows("baseline002")
    probe_rows = make_rows("probe003")
    return {
        "size": size,
        "datasets": datasets,
        "backends": ["baseline002", "probe003"],
        "baseline_summary": {ds: met.summarize(
            [r for r in baseline_rows if r["dataset"] == ds]) for ds in datasets},
        "probe_summary": {ds: met.summarize(
            [r for r in probe_rows if r["dataset"] == ds]) for ds in datasets},
        "baseline_rows": baseline_rows,
        "probe_rows": probe_rows,
    }


def _probe_payload(probe):
    return {
        "meta": {
            "mission": "test", "seed_dev": sp.DEV_SEED, "seed_blind": sp.BLIND_SEED,
            "config": CONFIG, "config_sha256": run_spike._config_sha(),
            "fingerprints": run_spike._fingerprints(),
            "generated_at_utc": "test",
        },
        "results": {}, "summary": {}, "probe": probe,
    }


def test_check_results_probe_valid(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code == 0, msg


def test_check_results_probe_corrupt_summary(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["probe_summary"]["audit003"]["synthetic_tp"] = 999
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_probe_duplicate_row(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["baseline_rows"].append(
        dict(payload["probe"]["baseline_rows"][0]))
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_probe_missing_row(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["probe_rows"] = payload["probe"]["probe_rows"][:-1]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_probe_wrong_backend(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["probe_rows"][0]["backend"] = "baseline002"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


# --------------------------------------------------------------------------- #
# Rework-2 — score trompeur, profile duplicates, backends ordonnés, fp exacts
# --------------------------------------------------------------------------- #
def test_probe_trail_has_baseline_score_not_score():
    # The probe trail must publish baseline_score (002 diagnostic) and NO
    # "score" field (which was the misleading 002 composite including the old
    # shape gates).
    import run_probe_impl
    img, gt = run_probe_impl._syn.build_case("dev", "diag_strong", 192)
    res = run_probe_impl.probe_detect(img, 192, run_probe_impl._syn.DEV_SEED)
    assert res["state"] == "ok"
    assert res["n_trails"] >= 1
    for t in res["trails"]:
        assert "baseline_score" in t
        assert "score" not in t
        assert isinstance(t["baseline_score"], (int, float))


def test_check_results_profile_duplicate_case_fails(tmp_path):
    # Inject a duplicate case while keeping all IDs present and recomputing the
    # summary so a set-only check would pass; the checker must still reject.
    payload = _minimal_payload()
    sk = "dev"
    dup = dict(payload["results"][sk][0])
    payload["results"][sk].append(dup)
    # recompute summary so set-of-ids would match
    payload["summary"][sk] = run_spike._confusion_summary(payload["results"][sk])
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code != 0
    assert "duplicate" in msg


def test_check_results_profile_non_object_row_fails(tmp_path):
    payload = _minimal_payload()
    payload["results"]["dev"][0] = "not-an-object"
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code != 0
    assert "row must be an object" in msg


def test_check_results_probe_backends_reordered_fails(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["backends"] = ["probe003", "baseline002"]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_probe_backends_duplicate_fails(tmp_path):
    payload = _probe_payload(_minimal_probe_payload())
    payload["probe"]["backends"] = ["baseline002", "baseline002"]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(payload))
    code, _ = run_spike.check_results(str(p))
    assert code != 0


def test_check_results_fingerprints_unexpected_key_fails(tmp_path):
    payload = _minimal_payload()
    payload["meta"]["fingerprints"]["../unexpected/file.py"] = "0" * 64
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code != 0
    assert "keys differ" in msg or "unexpected" in msg


def test_check_results_fingerprints_missing_key_fails(tmp_path):
    payload = _minimal_payload()
    # drop one required fingerprint key
    payload["meta"]["fingerprints"].pop(next(iter(payload["meta"]["fingerprints"])))
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    code, msg = run_spike.check_results(str(p))
    assert code != 0
    assert "keys differ" in msg or "missing" in msg
