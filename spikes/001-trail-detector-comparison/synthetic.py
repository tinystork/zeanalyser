"""Synthetic deterministic corpus for the satdet-vs-MRT trail detector spike.

This module builds a small, CPU-only, deterministic suite of 2D images.  Every
image is produced from a per-case seed derived from a single master seed, so the
whole corpus is reproducible.

The suite is deliberately small but discriminating.  It does **not** attempt to
reproduce real Seestar/ACS data: negatives are simplified stand-ins for common
confusion classes (aligned stars, column defect, low-frequency gradient, dense
field).  No claim about real-data performance should be read into these cases.

Ground truth is stored per case as ``gt_has_trail`` (bool) plus a list of
``gt_trails``, each carrying the physical trail orientation
(``angle_deg`` in [0, 180), computed with :func:`angle_from_endpoints`).

Coordinate conventions
----------------------
* ``x`` is the column index, ``y`` the row index (numpy ``[y, x]`` ordering).
* ``angle_deg`` is ``atan2(dy, dx)`` normalised to [0, 180), i.e. the physical
  orientation of the streak in image coordinates (0 = horizontal, 90 = vertical).
"""

from __future__ import annotations

import numpy as np


# --------------------------------------------------------------------------- #
# Primitive drawers (pure numpy, no I/O)
# --------------------------------------------------------------------------- #
def angle_from_endpoints(p0, p1):
    """Physical line orientation in [0, 180) degrees from two endpoints.

    ``p0``/``p1`` are ``(x, y)`` tuples.  The angle is ``atan2(dy, dx)`` folded
    into ``[0, 180)`` so that a line and its reverse are identical.
    """
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    ang = float(np.degrees(np.arctan2(dy, dx))) % 180.0
    return ang


def _streak_distance_grid(shape, p0, p1):
    """Per-pixel euclidean distance to the segment ``p0 -> p1``."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]), float(p1[1])
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby
    t = ((xx - ax) * abx + (yy - ay) * aby) / ab2
    t = np.clip(t, 0.0, 1.0)
    cx = ax + t * abx
    cy = ay + t * aby
    return np.hypot(xx - cx, yy - cy)


def draw_streak(image, p0, p1, flux, width):
    """Add a Gaussian cross-section streak (peak ``flux`` counts) to ``image``.

    ``width`` is the Gaussian sigma (pixels) perpendicular to the streak.  The
    streak is added in-place.
    """
    d = _streak_distance_grid(image.shape, p0, p1)
    image += flux * np.exp(-0.5 * (d / width) ** 2)
    return image


def make_background(shape, seed, mean=30.0, readnoise=3.0):
    """Poisson sky background + Gaussian read noise."""
    rng = np.random.default_rng(seed)
    img = rng.poisson(mean, shape).astype(float)
    img += rng.normal(0.0, readnoise, shape)
    return img


def add_stars(image, positions, peak, psf_sigma=1.5):
    """Add point sources (Gaussian PSF) at ``positions`` (list of (x, y))."""
    yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    for (sx, sy) in positions:
        d2 = (xx - sx) ** 2 + (yy - sy) ** 2
        image += peak * np.exp(-0.5 * d2 / psf_sigma ** 2)
    return image


# --------------------------------------------------------------------------- #
# Case definitions
# --------------------------------------------------------------------------- #
# Trail fluxes are expressed relative to a Poisson background of ~30 counts and
# read noise ~3 counts (noise sigma ~ 6).  "strong" ~ 400 is far above noise,
# "weak" ~ 60 is only a few sigma and is expected to be marginal for both
# detectors.
STRONG_FLUX = 400.0
WEAK_FLUX = 60.0
TRAIL_WIDTH = 1.5


def _trail_gt(p0, p1, label):
    return {"label": label, "p0": tuple(p0), "p1": tuple(p1),
            "angle_deg": angle_from_endpoints(p0, p1)}


def build_case(case_id, size, seed):
    """Build a single case image plus its ground-truth dict.

    Returns ``(image, gt)`` where ``gt`` is a dict with ``case_id``,
    ``gt_has_trail`` and ``gt_trails``.
    """
    n = size
    gt = {"case_id": case_id, "gt_has_trail": False, "gt_trails": []}

    if case_id == "diag_strong":
        img = make_background((n, n), seed)
        p0, p1 = (8, 8), (n - 9, n - 9)
        draw_streak(img, p0, p1, STRONG_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "horiz_strong":
        img = make_background((n, n), seed)
        p0, p1 = (4, n // 2), (n - 5, n // 2)
        draw_streak(img, p0, p1, STRONG_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "horizontal")])

    elif case_id == "vert_strong":
        img = make_background((n, n), seed)
        p0, p1 = (n // 2, 4), (n // 2, n - 5)
        draw_streak(img, p0, p1, STRONG_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "vertical")])

    elif case_id == "diag_weak":
        img = make_background((n, n), seed)
        p0, p1 = (8, 8), (n - 9, n - 9)
        draw_streak(img, p0, p1, WEAK_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "diag_short":
        img = make_background((n, n), seed)
        # A short (~40% of the diagonal) streak, well inside the frame.
        m = n // 2
        r = int(round(0.2 * n))
        p0, p1 = (m - r, m - r), (m + r, m + r)
        draw_streak(img, p0, p1, STRONG_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "diag_partial":
        img = make_background((n, n), seed)
        # One endpoint on the border, the other in the interior (not edge-to-edge).
        p0, p1 = (n - 5, 5), (n // 2, n // 2 + 20)
        draw_streak(img, p0, p1, STRONG_FLUX, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[_trail_gt(p0, p1, "diagonal")])

    elif case_id == "two_trails":
        img = make_background((n, n), seed)
        p0a, p1a = (8, 8), (n - 9, n - 9)        # strong anti-diagonal? -> 45
        p0b, p1b = (8, n - 9), (n - 9, 8)        # other diagonal -> ~135
        draw_streak(img, p0a, p1a, STRONG_FLUX, TRAIL_WIDTH)
        draw_streak(img, p0b, p1b, 150.0, TRAIL_WIDTH)
        gt.update(gt_has_trail=True, gt_trails=[
            _trail_gt(p0a, p1a, "diagonal-a"),
            _trail_gt(p0b, p1b, "diagonal-b"),
        ])

    elif case_id == "noise_stars":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 1)
        pos = [(float(rng.uniform(10, n - 10)), float(rng.uniform(10, n - 10)))
               for _ in range(15)]
        add_stars(img, pos, peak=400.0, psf_sigma=1.5)
        # gt_has_trail stays False

    elif case_id == "aligned_stars":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 1)
        # Stars placed on a straight diagonal with small perpendicular jitter.
        pos = []
        for f in np.linspace(0.12, 0.88, 12):
            x = f * n
            y = f * n
            x += rng.uniform(-1.5, 1.5)
            y += rng.uniform(-1.5, 1.5)
            pos.append((float(x), float(y)))
        add_stars(img, pos, peak=350.0, psf_sigma=1.5)
        # gt_has_trail stays False

    elif case_id == "column_defect":
        img = make_background((n, n), seed)
        # A hot column spanning the full height (vertical line defect).
        col = n // 2
        img[:, col:col + 2] += 120.0
        # gt_has_trail stays False

    elif case_id == "filament_gradient":
        img = make_background((n, n), seed)
        # A smooth low-frequency linear gradient (no sharp edge).
        yy, xx = np.mgrid[0:n, 0:n]
        img += 40.0 * (xx + yy) / (2.0 * n)
        # gt_has_trail stays False

    elif case_id == "dense_field":
        img = make_background((n, n), seed)
        rng = np.random.default_rng(seed + 1)
        pos = [(float(rng.uniform(4, n - 4)), float(rng.uniform(4, n - 4)))
               for _ in range(150)]
        add_stars(img, pos, peak=300.0, psf_sigma=1.5)
        # gt_has_trail stays False

    else:
        raise ValueError(f"Unknown case id: {case_id!r}")

    return img, gt


# Ordered list of case ids (also the default run order).
CASE_IDS = [
    "diag_strong",
    "horiz_strong",
    "vert_strong",
    "diag_weak",
    "diag_short",
    "diag_partial",
    "two_trails",
    "noise_stars",
    "aligned_stars",
    "column_defect",
    "filament_gradient",
    "dense_field",
]
