"""End-to-end probe (TRAIL-02C): re-use spike-002 read-only, swap shape gates.

Re-uses the spike-002 pipeline (background/noise, multi-scale Hough candidates,
complete-link grouping, trail candidates) **read-only** by path, then recomputes
the *shape* decision with the model-003 transverse-profile discriminator,
replacing only the ``tophat``/``step_sharpness`` shape gates (contrast /
continuity / width / length gates are kept identical to 002).

**Fail-closed shape gate** — the shape decision is three-valued and *never*
promoted by default:

* ``column``    → adds reason ``shape=column`` (rejects the candidate);
* ``ambiguous`` → adds reason ``shape=ambiguous/defer`` (defers: the candidate
  is NOT accepted on shape alone, matching the "ambiguous jamais promu" rule);
* ``ridge``     → adds no shape reason (shape alone does not reject).

The probe is **fail-safe**: any exception yields ``state="error"`` with
``n_accepted=None`` and ``trails=[]``, which the 002 metrics never evaluate as a
TP/FP/FN/TN.  Each ``(case, dataset)`` is measured in-process and is well under
60 s; there is **no** subprocess timeout to claim.

Two evaluation sets (each row is tagged with an explicit ``dataset`` and
``backend`` so case ids that collide across sets — e.g. ``offaxis_91`` — cannot
be confused):

* ``spike002_blind`` — the 002 blind split (17 cases), re-built read-only.
* ``audit003``        — a fixed 003 audit (12 cases) of the failure classes 002
  could not resolve, at 192 and 256 px.

The result is the *difference* baseline-002 vs probe-003, not a new backend.
"""

from __future__ import annotations

import os
import sys

import numpy as np
from scipy import ndimage as _ndi

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE002_DIR = os.path.normpath(os.path.join(HERE, "..", "002-adaptive-hough-trail-detector"))

sys.path.insert(0, HERE)
sys.path.insert(0, SPIKE002_DIR)  # so 002's internal ``from detector import ...`` resolves

import profile_models as pm  # noqa: E402
from profile_models import discriminate_profile, default_offsets  # noqa: E402

# spike-002 modules, imported read-only by path (natural names, as 002 itself uses)
import detector as _det        # noqa: E402
import synthetic as _syn       # noqa: E402
import metrics as _met         # noqa: E402


# dataset / backend tags (single source of truth for the checker)
DATASET_002_BLIND = "spike002_blind"
DATASET_AUDIT003 = "audit003"
BACKEND_BASELINE = "baseline002"
BACKEND_PROBE = "probe003"


# --------------------------------------------------------------------------- #
# Probe measurement: 002 pipeline up to trails, then 003 shape decision
# --------------------------------------------------------------------------- #
def _probe_shape_decision(residual, trail, noise):
    """Return ``(label, decision, coverage)`` for one 002 trail, model-003 shape.

    ``noise`` is the image/residual MAD from 002's preprocess (global, robust to
    the sparse structure); it is passed through to the discriminator so the
    probe and the profile runner use the *same* noise source.
    """
    offsets = default_offsets()
    profile, coverage = pm.sample_transverse_profile_subpixel(
        residual, trail["p0"], trail["p1"], offsets=offsets)
    decision = discriminate_profile(profile, offsets, noise=noise)
    return decision["label"], decision, coverage


def _probe_detect(image, size, seed):
    residual, noise = _det.preprocess(image, _det.CONFIG)
    segments = _det.edge_segments(residual, noise, size, seed, _det.CONFIG)
    lines = _det.group_into_lines(segments, _det.CONFIG)
    trails_raw = _det.group_into_trails(lines, _det.CONFIG)

    cfg = _det.CONFIG
    out_trails = []
    for t in trails_raw:
        # reuse 002's own measurements for contrast/continuity/width/length
        base = _det.measure_and_validate(residual, noise, t, size, cfg)
        features = base["features"]
        label, decision, coverage = _probe_shape_decision(residual, t, noise)

        reasons = []
        if features["contrast_snr"] < cfg["min_contrast_snr"]:
            reasons.append(f"contrast {features['contrast_snr']:.1f} < "
                           f"{cfg['min_contrast_snr']:.1f}")
        if features["continuity"] < cfg["min_continuity"]:
            reasons.append(f"continuity {features['continuity']:.2f} < "
                           f"{cfg['min_continuity']:.2f}")
        if not (cfg["min_width"] <= features["width_fwhm"] <= cfg["max_width"]):
            reasons.append(f"width {features['width_fwhm']:.1f} outside "
                           f"[{cfg['min_width']},{cfg['max_width']}]")
        # shape gate — fail-closed: column rejects, ambiguous defers (never
        # accepted by default), ridge passes on shape.
        if label == "column":
            reasons.append("shape=column (model-003)")
        elif label == "ambiguous":
            reasons.append("shape=ambiguous/defer (model-003)")
        if features["length"] < size * cfg["min_length_frac"]:
            reasons.append(f"length {features['length']:.0f} < "
                           f"{size * cfg['min_length_frac']:.0f}")

        accepted = len(reasons) == 0
        trail_out = {
            "phi": t["phi"], "rho": t["rho"], "p0": t["p0"], "p1": t["p1"],
            "length": t["length"], "n_lines": t["n_lines"],
            "n_segments": t["n_segments"],
            # diagnostic 002 score, inherited read-only — NOT a 003 score/decision.
            # The 003 shape gate is driven by shape_label/shape_preference only.
            "baseline_score": base["score"],
            "accepted": accepted, "reasons": reasons,
            "shape_label": label, "shape_preference": decision["preference"],
            "shape_snr": decision.get("snr"), "shape_coverage": coverage,
        }
        out_trails.append(trail_out)

    n_accepted = sum(1 for t in out_trails if t["accepted"])
    return {
        "state": "ok",
        "noise": float(noise),
        "n_trails": len(out_trails),
        "n_accepted": n_accepted,
        "trails": out_trails,
    }


def probe_detect(image, size, seed):
    """Fail-safe wrapper around :func:`_probe_detect`.

    Any exception → ``state="error"``, ``n_accepted=None``, ``trails=[]``; the
    002 metrics leave non-ok rows unevaluated (never a TP/FP/FN/TN)."""
    try:
        return _probe_detect(image, size, seed)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "state": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "noise": None,
            "n_trails": None,
            "n_accepted": None,
            "trails": [],
        }


def _run_baseline(image, size, seed):
    return _det.detect(image, size, seed)


def _assess_probe(gt, probe):
    """Assess a probe result with metrics002.

    ``metrics002.match_trails`` (read-only) reads ``trail["score"]`` for its
    ``detected_score`` diagnostic, but the probe trail publishes
    ``baseline_score`` only (a ``score`` field would misleadingly look like a
    003 decision score).  Inject a transient ``score`` alias for the assessment
    and drop it afterwards, so the stored probe rows never expose ``score``.
    """
    trails = probe.get("trails") or []
    for t in trails:
        t["score"] = t.get("baseline_score")
    try:
        return _met.assess_case(gt, probe)
    finally:
        for t in trails:
            t.pop("score", None)


# --------------------------------------------------------------------------- #
# 003 audit builders (fixed failure classes from 002, read-only primitives)
# --------------------------------------------------------------------------- #
def _audit_ridge(size, seed, sigma, angle_deg, amplitude=400.0):
    img = _syn._syn001.make_background((size, size), seed)
    a = np.radians(angle_deg)
    ux, uy = np.cos(a), np.sin(a)
    L = 0.40 * size
    cx, cy = size / 2.0, size / 2.0
    p0 = (cx - ux * L, cy - uy * L)
    p1 = (cx + ux * L, cy + uy * L)
    _syn._syn001.draw_streak(img, p0, p1, amplitude, sigma)
    return img, p0, p1


def _audit_column(size, seed, width, blur=0.0, amplitude=120.0):
    """Softened column defect: smooth the defect **mask** only, not the
    background/noise (a whole-image gaussian filter would favour the defect
    artificially)."""
    img = _syn._syn001.make_background((size, size), seed)
    col = int(round(0.40 * size))
    mask = np.zeros((size, size), dtype=float)
    mask[:, col:col + width] = 1.0
    if blur > 0:
        mask = _ndi.gaussian_filter(mask, sigma=blur)
    img += amplitude * mask
    p0 = (col + width / 2.0, 4)
    p1 = (col + width / 2.0, size - 5)
    return img, p0, p1


def _audit_row(size, seed, width, amplitude=120.0):
    img = _syn._syn001.make_background((size, size), seed)
    row = int(round(0.55 * size))
    img[row:row + width, :] += amplitude
    p0 = (4, row + width / 2.0)
    p1 = (size - 5, row + width / 2.0)
    return img, p0, p1


def _audit_variable_band(size, seed, width=4, amplitude=120.0):
    """Vertical band whose longitudinal gain varies (harder column defect)."""
    img = _syn._syn001.make_background((size, size), seed)
    col = int(round(0.60 * size))
    yy = np.arange(size, dtype=float)
    env = 0.5 + 0.5 * np.sin(2.0 * np.pi * yy / size) ** 2
    mask = np.zeros((size, size), dtype=float)
    mask[:, col:col + width] = env[:, None]
    img += amplitude * mask
    p0 = (col + width / 2.0, 4)
    p1 = (col + width / 2.0, size - 5)
    return img, p0, p1


def _audit_dense(size, seed, n=220, amplitude=300.0):
    img = _syn._syn001.make_background((size, size), seed)
    rng = np.random.default_rng(seed + 41)
    pos = [(float(rng.uniform(4, size - 4)), float(rng.uniform(4, size - 4)))
           for _ in range(n)]
    _syn._syn001.add_stars(img, pos, peak=amplitude, psf_sigma=1.5)
    return img, (0.1 * size, 0.1 * size), (0.9 * size, 0.9 * size)


def _trail_gt(p0, p1, label):
    return {"label": label, "p0": tuple(p0), "p1": tuple(p1),
            "angle_deg": _syn._syn001.angle_from_endpoints(p0, p1)}


def _build_audit(size):
    """Return ``{case_id: {pos, gt_trails, img}}`` for the 003 audit.

    Positives carry geometric ground-truth trails (p0/p1) so spike-002's
    bounded geometric matching (angle <= 3 deg, offset <= 5 px) applies."""
    cases = {}
    # positives (real trails) — carry GT endpoints
    img, p0, p1 = _audit_ridge(size, 20261006, 0.6, 38.0)
    cases["thin_s06_38"] = {"pos": True, "img": img,
                            "gt_trails": [_trail_gt(p0, p1, "thin-0.6-38")]}
    img, p0, p1 = _audit_ridge(size, 20261006 + 1, 0.8, 89.5)
    cases["thin_s08_895"] = {"pos": True, "img": img,
                             "gt_trails": [_trail_gt(p0, p1, "thin-0.8-89.5")]}
    img, p0, p1 = _audit_ridge(size, 20261006 + 2, 1.5, 91.0, 300.0)
    cases["offaxis_91"] = {"pos": True, "img": img,
                           "gt_trails": [_trail_gt(p0, p1, "offaxis-91")]}
    img, p0, p1 = _audit_ridge(size, 20261006 + 3, 1.5, 45.0)
    cases["ridge_s15_sub"] = {"pos": True, "img": img,
                              "gt_trails": [_trail_gt(p0, p1, "ridge-1.5")]}
    img, p0, p1 = _audit_ridge(size, 20261006 + 4, 3.5, 45.0, 350.0)
    cases["wide_s35"] = {"pos": True, "img": img,
                         "gt_trails": [_trail_gt(p0, p1, "wide-3.5")]}
    # negatives (defects)
    cases["hard_col1"] = {"pos": False, "img": _audit_column(size, 20261006 + 5, 1)[0],
                          "gt_trails": []}
    cases["hard_col2"] = {"pos": False, "img": _audit_column(size, 20261006 + 6, 2)[0],
                          "gt_trails": []}
    cases["soft_col4_b1"] = {"pos": False, "img": _audit_column(size, 20261006 + 7, 4, blur=1.0)[0],
                             "gt_trails": []}
    cases["soft_col6_b2"] = {"pos": False, "img": _audit_column(size, 20261006 + 8, 6, blur=2.0)[0],
                             "gt_trails": []}
    cases["hard_row2"] = {"pos": False, "img": _audit_row(size, 20261006 + 9, 2)[0],
                          "gt_trails": []}
    cases["variable_band"] = {"pos": False, "img": _audit_variable_band(size, 20261006 + 10)[0],
                              "gt_trails": []}
    cases["dense_field"] = {"pos": False, "img": _audit_dense(size, 20261006 + 11)[0],
                            "gt_trails": []}
    return cases


def run(size):
    """Run baseline-002 + probe-003 on both datasets; return the difference.

    Rows are tagged with ``dataset``/``backend``; summaries are recomputable by
    the runner's checker via ``metrics002.summarize``.  In-process, no subprocess
    timeout (each case is well under 60 s)."""
    seed = _syn.BLIND_SEED

    # --- spike-002 blind, read-only ---
    b_rows, p_rows = [], []
    for cid in _syn.BLIND_CASE_IDS:
        image, gt = _syn.build_case("blind", cid, size)
        base = _run_baseline(image, size, seed)
        probe = probe_detect(image, size, seed)
        base = _met.assess_case(gt, base)
        probe = _assess_probe(gt, probe)
        base["case_id"] = cid
        base["dataset"] = DATASET_002_BLIND
        base["backend"] = BACKEND_BASELINE
        probe["case_id"] = cid
        probe["dataset"] = DATASET_002_BLIND
        probe["backend"] = BACKEND_PROBE
        b_rows.append(base)
        p_rows.append(probe)

    # --- 003 fixed audit ---
    audit = _build_audit(size)
    a_b_rows, a_p_rows = [], []
    for cid, info in audit.items():
        image = info["img"]
        gt = {"gt_has_trail": info["pos"], "gt_trails": info["gt_trails"]}
        base = _run_baseline(image, size, seed)
        probe = probe_detect(image, size, seed)
        base = _met.assess_case(gt, base)
        probe = _assess_probe(gt, probe)
        base["case_id"] = cid
        base["dataset"] = DATASET_AUDIT003
        base["backend"] = BACKEND_BASELINE
        probe["case_id"] = cid
        probe["dataset"] = DATASET_AUDIT003
        probe["backend"] = BACKEND_PROBE
        a_b_rows.append(base)
        a_p_rows.append(probe)

    baseline_summary = {
        DATASET_002_BLIND: _met.summarize(b_rows),
        DATASET_AUDIT003: _met.summarize(a_b_rows),
    }
    probe_summary = {
        DATASET_002_BLIND: _met.summarize(p_rows),
        DATASET_AUDIT003: _met.summarize(a_p_rows),
    }
    return {
        "size": size,
        "datasets": {
            DATASET_002_BLIND: list(_syn.BLIND_CASE_IDS),
            DATASET_AUDIT003: list(audit.keys()),
        },
        "backends": [BACKEND_BASELINE, BACKEND_PROBE],
        "baseline_summary": baseline_summary,
        "probe_summary": probe_summary,
        "baseline_rows": b_rows + a_b_rows,
        "probe_rows": p_rows + a_p_rows,
    }
