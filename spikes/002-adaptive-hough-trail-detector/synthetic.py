"""Synthetic corpus for the adaptive-Hough trail spike (TRAIL-02B).

Three distinct splits:

* ``dev``               — canonical spike-001 corpus (12 cases), imported
  **read-only** by explicit path (no duplication).  Seed ``20261002``.
* ``observed_holdout``  — the original 02B holdout (13 cases, seed ``20261003``).
  **Contaminated / tuning-validation**: it was read during development (a
  measurement-robustness fix was informed by it).  Kept for continuity of the
  r0 report, clearly labelled; no longer treated as an independent test.
* ``blind``             — new, frozen split (seed ``20261004``) defined BEFORE
  the first blind run.  ``detector.CONFIG``, thresholds and mechanisms MUST NOT
  change after the first blind run.  This is the only independent test.

Anti-overfit discipline: DEV is used for the (at most two) documented config
attempts; ``blind`` is read exactly once with the frozen config and must not be
tuned on.  ``observed_holdout`` is retained only as a documented tuning
witness.
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np
from scipy import ndimage as _ndi

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE001_DIR = os.path.normpath(os.path.join(HERE, "..", "001-trail-detector-comparison"))

DEV_SEED = 20261002
OBSERVED_HOLDOUT_SEED = 20261003
BLIND_SEED = 20261004


def _load_spike001_synthetic():
    """Import spike-001 ``synthetic`` read-only by explicit path (no copying)."""
    path = os.path.join(SPIKE001_DIR, "synthetic.py")
    spec = importlib.util.spec_from_file_location("spike001_synthetic", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_syn001 = _load_spike001_synthetic()

draw_streak = _syn001.draw_streak
make_background = _syn001.make_background
add_stars = _syn001.add_stars
angle_from_endpoints = _syn001.angle_from_endpoints


def _trail_gt(p0, p1, label):
    return {"label": label, "p0": tuple(p0), "p1": tuple(p1),
            "angle_deg": angle_from_endpoints(p0, p1)}


def _add_blob_arc(image, cx, cy, radius, a0_deg, a1_deg, peak, sigma, step_deg=0.4):
    """Add a smooth curved filament: overlapping Gaussian blobs along an arc."""
    yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    n = 0
    for a in np.arange(a0_deg, a1_deg + 1e-9, step_deg):
        px = cx + radius * np.cos(np.radians(a))
        py = cy + radius * np.sin(np.radians(a))
        if 0 <= px < image.shape[1] and 0 <= py < image.shape[0]:
            image += peak * np.exp(-0.5 * ((xx - px) ** 2 + (yy - py) ** 2) / sigma ** 2)
            n += 1
    return image


# --------------------------------------------------------------------------- #
# DEV split: canonical 001 corpus, imported read-only
# --------------------------------------------------------------------------- #
DEV_CASE_IDS = list(_syn001.CASE_IDS)


def build_dev_case(case_id, size, seed=DEV_SEED):
    return _syn001.build_case(case_id, size, seed)


# --------------------------------------------------------------------------- #
# OBSERVED_HOLDOUT split: original 02B holdout (contaminated, kept as witness)
# --------------------------------------------------------------------------- #
OBSERVED_HOLDOUT_CASE_IDS = [
    "h_axis", "v_axis", "diag_weak_b", "diag_short_b", "diag_partial_b",
    "two_trails_b", "diag_wide_b",
    "noise_stars_b", "aligned_stars_b", "column_defect_b", "column_defect_1px",
    "filament_gradient_b", "dense_field_b",
]
OBSERVED_HOLDOUT_POSITIVES = {
    "h_axis", "v_axis", "diag_weak_b", "diag_short_b", "diag_partial_b",
    "two_trails_b", "diag_wide_b",
}


def build_observed_holdout_case(case_id, size, seed=OBSERVED_HOLDOUT_SEED):
    n = size
    gt = {"case_id": case_id, "gt_has_trail": False, "gt_trails": []}

    if case_id == "h_axis":
        img = make_background((n, n), seed)
        p0, p1 = (5, int(round(0.30 * n))), (n - 6, int(round(0.30 * n)))
        draw_streak(img, p0, p1, 430.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "horizontal")])

    elif case_id == "v_axis":
        img = make_background((n, n), seed)
        p0, p1 = (int(round(0.72 * n)), 6), (int(round(0.72 * n)), n - 7)
        draw_streak(img, p0, p1, 430.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "vertical")])

    elif case_id == "diag_weak_b":
        img = make_background((n, n), seed)
        p0, p1 = (10, n - 12), (n - 10, 12)
        draw_streak(img, p0, p1, 55.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "diag_short_b":
        img = make_background((n, n), seed)
        m = n // 2
        r = int(round(0.15 * n))
        p0, p1 = (m - r, m + r), (m + r, m - r)
        draw_streak(img, p0, p1, 400.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "diag_partial_b":
        img = make_background((n, n), seed)
        p0 = (int(round(0.18 * n)), int(round(0.82 * n)))
        p1 = (int(round(0.62 * n)), int(round(0.56 * n)))
        draw_streak(img, p0, p1, 400.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "two_trails_b":
        img = make_background((n, n), seed)
        p0a, p1a = (8, int(round(0.28 * n))), (n - 9, int(round(0.60 * n)))
        p0b, p1b = (8, int(round(0.72 * n))), (n - 9, int(round(0.40 * n)))
        draw_streak(img, p0a, p1a, 400.0, 1.5)
        draw_streak(img, p0b, p1b, 170.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[
            _trail_gt(p0a, p1a, "trail-a"),
            _trail_gt(p0b, p1b, "trail-b"),
        ])

    elif case_id == "diag_wide_b":
        img = make_background((n, n), seed)
        p0, p1 = (12, 12), (n - 13, n - 13)
        draw_streak(img, p0, p1, 400.0, 3.0)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal-wide")])

    elif case_id == "noise_stars_b":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 11)
        pos = [(float(rng.uniform(10, n - 10)), float(rng.uniform(10, n - 10)))
               for _ in range(22)]
        add_stars(img, pos, peak=400.0, psf_sigma=1.5)

    elif case_id == "aligned_stars_b":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 13)
        pos = []
        for f in np.linspace(0.14, 0.86, 14):
            x = f * n
            y = 0.5 * n + np.tan(np.radians(20.0)) * (f - 0.5) * n
            x += rng.uniform(-1.5, 1.5)
            y += rng.uniform(-1.5, 1.5)
            pos.append((float(x), float(y)))
        add_stars(img, pos, peak=350.0, psf_sigma=1.5)

    elif case_id == "column_defect_b":
        img = make_background((n, n), seed)
        col = int(round(0.40 * n))
        img[:, col:col + 2] += 120.0

    elif case_id == "column_defect_1px":
        img = make_background((n, n), seed)
        col = int(round(0.60 * n))
        img[:, col] += 120.0

    elif case_id == "filament_gradient_b":
        img = make_background((n, n), seed)
        yy, xx = np.mgrid[0:n, 0:n]
        img += 30.0 * ((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / (n ** 2)

    elif case_id == "dense_field_b":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 17)
        pos = [(float(rng.uniform(4, n - 4)), float(rng.uniform(4, n - 4)))
               for _ in range(180)]
        add_stars(img, pos, peak=300.0, psf_sigma=1.5)

    else:
        raise ValueError(f"Unknown observed_holdout case id: {case_id!r}")

    return img, gt


# --------------------------------------------------------------------------- #
# BLIND split: frozen, defined before first blind run (seed 20261004)
# --------------------------------------------------------------------------- #
BLIND_CASE_IDS = [
    # positives
    "near_wrap_179", "offaxis_91", "weak_73", "short_67", "partial_112",
    "two_mixed", "thin_38", "wide_141",
    # negatives
    "noise_stars_c", "aligned_stars_67", "hard_column_1px", "soft_column_4px",
    "hard_row_2px", "tracking_dashes", "curved_filament", "dense_field_c",
    "gradient_c",
]
BLIND_POSITIVES = {
    "near_wrap_179", "offaxis_91", "weak_73", "short_67", "partial_112",
    "two_mixed", "thin_38", "wide_141",
}


def build_blind_case(case_id, size, seed=BLIND_SEED):
    n = size
    gt = {"case_id": case_id, "gt_has_trail": False, "gt_trails": []}
    d45 = np.hypot(1.0, 1.0)

    if case_id == "near_wrap_179":
        img = make_background((n, n), seed)
        p0, p1 = (8, n // 2 + 2), (n - 9, n // 2 - 1)   # ~179 deg (quasi-horizontal)
        draw_streak(img, p0, p1, 400.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "near-horizontal")])

    elif case_id == "offaxis_91":
        img = make_background((n, n), seed)
        p0, p1 = (n // 2 + 1, 6), (n // 2 - 2, n - 7)   # ~91 deg (quasi-vertical)
        draw_streak(img, p0, p1, 300.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "near-vertical")])

    elif case_id == "weak_73":
        img = make_background((n, n), seed)
        dx = int(round((n - 16) / 3.271))               # ~73 deg slope
        p0, p1 = (int(round(0.28 * n)), 8), (int(round(0.28 * n)) + dx, n - 8)
        draw_streak(img, p0, p1, 45.0, 2.0)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "weak-73")])

    elif case_id == "short_67":
        img = make_background((n, n), seed)
        hx = int(round(0.17 * n * np.cos(np.radians(67.0))))
        hy = int(round(0.17 * n * np.sin(np.radians(67.0))))
        p0, p1 = (n // 2 - hx, n // 2 - hy), (n // 2 + hx, n // 2 + hy)  # ~0.34n, ~67 deg
        draw_streak(img, p0, p1, 400.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "short-67")])

    elif case_id == "partial_112":
        img = make_background((n, n), seed)
        dx = -int(round(0.48 * n * abs(np.cos(np.radians(112.0)))))
        dy = int(round(0.48 * n * np.sin(np.radians(112.0))))
        p0 = (int(round(0.70 * n)), 4)                 # endpoint on top border
        p1 = (p0[0] + dx, p0[1] + dy)
        draw_streak(img, p0, p1, 400.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "partial-112")])

    elif case_id == "two_mixed":
        img = make_background((n, n), seed)
        # trail A ~12 deg
        dya = int(round(np.tan(np.radians(12.0)) * (n - 17)))
        p0a, p1a = (8, int(round(0.40 * n))), (n - 9, int(round(0.40 * n)) + dya)
        # trail B ~98 deg
        dxb = -int(round(np.tan(np.radians(8.0)) * (n - 13)))
        p0b, p1b = (int(round(0.62 * n)), 6), (int(round(0.62 * n)) + dxb, n - 7)
        draw_streak(img, p0a, p1a, 400.0, 1.5)
        draw_streak(img, p0b, p1b, 150.0, 1.5)
        gt.update(gt_has_trail=True, gt_trails=[
            _trail_gt(p0a, p1a, "mixed-a"),
            _trail_gt(p0b, p1b, "mixed-b"),
        ])

    elif case_id == "thin_38":
        img = make_background((n, n), seed)
        dy = int(round(np.tan(np.radians(38.0)) * (n - 20)))
        p0, p1 = (10, int(round(0.25 * n))), (n - 10, int(round(0.25 * n)) + dy)
        draw_streak(img, p0, p1, 300.0, 0.8)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "thin-38")])

    elif case_id == "wide_141":
        img = make_background((n, n), seed)
        dx = -int(round(0.45 * n * abs(np.cos(np.radians(141.0)))))
        dy = int(round(0.45 * n * np.sin(np.radians(141.0))))
        p0 = (int(round(0.85 * n)), 8)
        p1 = (p0[0] + dx, p0[1] + dy)
        draw_streak(img, p0, p1, 350.0, 3.5)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "wide-141")])

    elif case_id == "noise_stars_c":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 31)
        pos = [(float(rng.uniform(8, n - 8)), float(rng.uniform(8, n - 8)))
               for _ in range(30)]
        add_stars(img, pos, peak=400.0, psf_sigma=1.5)

    elif case_id == "aligned_stars_67":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 37)
        pos = []
        for f in np.linspace(0.12, 0.88, 18):
            x = f * n
            y = 0.5 * n + np.tan(np.radians(67.0)) * (f - 0.5) * n
            x += rng.uniform(-1.5, 1.5)
            y += rng.uniform(-1.5, 1.5)
            pos.append((float(x), float(y)))
        add_stars(img, pos, peak=350.0, psf_sigma=1.5)

    elif case_id == "hard_column_1px":
        img = make_background((n, n), seed)
        col = int(round(0.45 * n))
        img[:, col] += 120.0

    elif case_id == "soft_column_4px":
        # 4-px plateau column with smoothed transitions (detector defect),
        # NOT an arbitrary infinite Gaussian.
        img = make_background((n, n), seed)
        col = int(round(0.35 * n))
        img[:, col:col + 4] += 120.0
        img = _ndi.gaussian_filter(img, sigma=1.0)

    elif case_id == "hard_row_2px":
        img = make_background((n, n), seed)
        row = int(round(0.55 * n))
        img[row:row + 2, :] += 120.0

    elif case_id == "tracking_dashes":
        # 3 elongated-PSF dashes, same 45 deg angle, clearly discontinuous.
        img = make_background((n, n), seed)
        dash = 0.31 * n
        gap = 0.23 * n
        t0 = 0.10 * n
        for i in range(3):
            s = t0 + i * (dash + gap)
            e = s + dash
            p0 = (s / d45, s / d45)
            p1 = (e / d45, e / d45)
            draw_streak(img, p0, p1, 350.0, 1.5)

    elif case_id == "curved_filament":
        img = make_background((n, n), seed)
        cx, cy = 0.5 * n, 0.8 * n
        radius = 0.30 * n
        _add_blob_arc(img, cx, cy, radius, 0.0, 180.0, 250.0, 1.5, step_deg=0.5)

    elif case_id == "dense_field_c":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 41)
        pos = [(float(rng.uniform(4, n - 4)), float(rng.uniform(4, n - 4)))
               for _ in range(220)]
        add_stars(img, pos, peak=300.0, psf_sigma=1.5)

    elif case_id == "gradient_c":
        img = make_background((n, n), seed)
        yy, xx = np.mgrid[0:n, 0:n]
        img += 40.0 * xx / n

    else:
        raise ValueError(f"Unknown blind case id: {case_id!r}")

    return img, gt


# --------------------------------------------------------------------------- #
# Split registry
# --------------------------------------------------------------------------- #
SPLITS = {
    "dev": {
        "case_ids": DEV_CASE_IDS,
        "seed": DEV_SEED,
        "builder": build_dev_case,
        "positives": None,  # inferred from gt_has_trail
    },
    "observed_holdout": {
        "case_ids": OBSERVED_HOLDOUT_CASE_IDS,
        "seed": OBSERVED_HOLDOUT_SEED,
        "builder": build_observed_holdout_case,
        "positives": OBSERVED_HOLDOUT_POSITIVES,
    },
    "blind": {
        "case_ids": BLIND_CASE_IDS,
        "seed": BLIND_SEED,
        "builder": build_blind_case,
        "positives": BLIND_POSITIVES,
    },
}


def build_case(split, case_id, size):
    """Build one case in a given split, returning ``(image, gt)``."""
    return SPLITS[split]["builder"](case_id, size)
