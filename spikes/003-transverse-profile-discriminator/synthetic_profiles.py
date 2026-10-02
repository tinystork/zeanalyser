"""Synthetic profile corpus for the transverse-profile discriminator (TRAIL-02C).

Two independent, deterministic profile-level splits:

* ``dev``   — small deterministic grid (seed ``20261005``) used ONLY to choose
  the ``pref_delta_threshold`` / decision config (at most two documented
  attempts), then frozen.
* ``blind`` — frozen grid (seed ``20261006``) defined BEFORE the first blind
  run, with **unseen** parameter combinations.  Thresholds / models / config
  MUST NOT change after the first blind run.

Every case is a small 2-D image plus a ground-truth transverse profile.  The
runner samples the transverse profile **sub-pixel** at the known centreline
(``sample_transverse_profile_subpixel``) and classifies it with
``discriminate_profile``.  Ground truth is therefore a *profile-level* label
(``ridge`` / ``column`` / ``ambiguous``) plus the true generating parameters.

Label rule (documented, deterministic, physical):
* ``ridge``     — a single Gaussian crest (continuous trail).
* ``column``    — a plateau band whose flat top is still resolvable, i.e. the
  band is hard (softness = 0) or its width exceeds ``2 * softness``.
* ``ambiguous`` — everything a transverse profile alone cannot separate from a
  smooth crest: no structure, double ridge, aligned stars, gradient, asymmetric
  profile, or a plateau softened until physically indistinguishable from a
  Gaussian (width <= 2 * softness).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as _ndi

from profile_models import default_offsets, sample_transverse_profile_subpixel

DEV_SEED = 20261005
BLIND_SEED = 20261006

# amplitude / noise variety (deterministic, picked per case by index)
AMPLITUDES = [400.0, 200.0, 60.0]
READNOISES = [1.5, 3.0, 6.0]


# --------------------------------------------------------------------------- #
# Image primitives (self-contained; numpy/scipy only)
# --------------------------------------------------------------------------- #
def make_background(shape, seed, mean=30.0, readnoise=3.0):
    rng = np.random.default_rng(seed)
    img = rng.poisson(mean, shape).astype(float)
    img += rng.normal(0.0, readnoise, shape)
    return img


def _seg_distance(shape, p0, p1):
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


def _signed_transverse_distance(shape, p0, p1):
    """Signed perpendicular distance (px) to the infinite line ``p0->p1``.

    Positive on one side of the directed segment, negative on the other — used
    to build genuinely asymmetric (two half-profile) crests, which an unsigned
    segment distance cannot express."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]), float(p1[1])
    abx, aby = bx - ax, by - ay
    nrm = float(np.hypot(abx, aby))
    ux, uy = abx / nrm, aby / nrm
    return (xx - ax) * uy - (yy - ay) * ux


def draw_ridge(image, p0, p1, amplitude, sigma):
    """Gaussian-cross-section crest (sigma = perpendicular width, px)."""
    d = _seg_distance(image.shape, p0, p1)
    image += amplitude * np.exp(-0.5 * (d / sigma) ** 2)
    return image


def draw_column(image, p0, p1, width, amplitude, softness=0.0):
    """Hard plateau band of ``width`` px along ``p0->p1``, with softened edges.

    Only the defect **mask** is gaussian-smoothed by ``softness`` px; the
    background and its noise are left untouched (a *different* physical
    realisation than the logistic model the discriminator fits).  Smoothing the
    whole image would give the defect an artificial advantage."""
    d = _seg_distance(image.shape, p0, p1)
    mask = np.where(d <= width / 2.0, 1.0, 0.0).astype(float)
    if softness > 0:
        mask = _ndi.gaussian_filter(mask, sigma=softness)
    image += amplitude * mask
    return image


def add_stars(image, positions, peak, psf_sigma=1.5):
    yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    for (sx, sy) in positions:
        d2 = (xx - sx) ** 2 + (yy - sy) ** 2
        image += peak * np.exp(-0.5 * d2 / psf_sigma ** 2)
    return image


def angle_from_endpoints(p0, p1):
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    return float(np.degrees(np.arctan2(dy, dx))) % 180.0


def _centreline(size, angle_deg, subpixel, length_frac=0.86):
    """Return ``(p0, p1)`` for a feature through the image centre at ``angle``,
    offset perpendicular by ``subpixel`` px (so the peak sits at a fractional
    pixel)."""
    n = size
    a = np.radians(angle_deg)
    ux, uy = np.cos(a), np.sin(a)
    nx, ny = -np.sin(a), np.cos(a)
    cx, cy = n / 2.0, n / 2.0
    ox, oy = cx + nx * subpixel, cy + ny * subpixel
    L = length_frac * n / 2.0
    p0 = (ox - ux * L, oy - uy * L)
    p1 = (ox + ux * L, oy + uy * L)
    return p0, p1


# --------------------------------------------------------------------------- #
# Preprocess (background subtraction + robust noise), mirroring spike-002
# --------------------------------------------------------------------------- #
def residual_and_noise(image, bg_size_frac=0.13):
    arr = np.asarray(image, dtype=float)
    size = max(arr.shape)
    bsize = max(15, int(round(size * bg_size_frac)))
    bsize = bsize if bsize % 2 == 1 else bsize + 1
    bg = _ndi.median_filter(arr, size=bsize)
    residual = arr - bg
    med = float(np.median(residual))
    mad = float(np.median(np.abs(residual - med)))
    noise = max(1.4826 * mad, 1e-6)
    return residual, noise


def sample_profile_from_image(image, p0, p1, offsets=None, n_long=None):
    """Residual + sub-pixel transverse profile + noise for a centreline."""
    residual, noise = residual_and_noise(image)
    profile, coverage = sample_transverse_profile_subpixel(
        residual, p0, p1, offsets=offsets, n_long=n_long)
    return profile, noise, coverage


# --------------------------------------------------------------------------- #
# Case builders
# --------------------------------------------------------------------------- #
def _ridge_case(size, seed, sigma, subpixel, angle_deg, amplitude, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    p0, p1 = _centreline(size, angle_deg, subpixel)
    draw_ridge(img, p0, p1, amplitude, sigma)
    return img, p0, p1, {
        "kind": "ridge", "label": "ridge", "sigma": sigma,
        "center_subpixel": subpixel, "angle_deg": angle_deg,
        "amplitude": amplitude, "readnoise": readnoise,
    }


def _column_case(size, seed, width, softness, subpixel, angle_deg,
                 amplitude, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    p0, p1 = _centreline(size, angle_deg, subpixel)
    draw_column(img, p0, p1, width, amplitude, softness=softness)
    label = "column" if (softness == 0 or width > 2 * softness) else "ambiguous"
    return img, p0, p1, {
        "kind": "column", "label": label, "width": width,
        "softness": softness, "center_subpixel": subpixel,
        "angle_deg": angle_deg, "amplitude": amplitude, "readnoise": readnoise,
    }


def _no_structure_case(size, seed, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    p0, p1 = _centreline(size, 45.0, 0.0)
    return img, p0, p1, {"kind": "no_structure", "label": "ambiguous",
                         "readnoise": readnoise}


def _double_ridge_case(size, seed, sep, amplitude, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    p0a, p1a = _centreline(size, 45.0, -sep / 2.0)
    p0b, p1b = _centreline(size, 45.0, +sep / 2.0)
    draw_ridge(img, p0a, p1a, amplitude, 1.2)
    draw_ridge(img, p0b, p1b, amplitude, 1.2)
    p0, p1 = _centreline(size, 45.0, 0.0)
    return img, p0, p1, {"kind": "double_ridge", "label": "ambiguous",
                         "sep": sep, "amplitude": amplitude,
                         "readnoise": readnoise}


def _aligned_stars_case(size, seed, amplitude, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    rng = np.random.default_rng(seed + 7)
    pos = []
    for f in np.linspace(0.15, 0.85, 12):
        x = f * size + rng.uniform(-1.0, 1.0)
        y = f * size + rng.uniform(-1.0, 1.0)
        pos.append((float(x), float(y)))
    add_stars(img, pos, peak=amplitude, psf_sigma=1.5)
    p0, p1 = (0.12 * size, 0.12 * size), (0.88 * size, 0.88 * size)
    return img, p0, p1, {"kind": "aligned_stars", "label": "ambiguous",
                         "amplitude": amplitude, "readnoise": readnoise}


def _gradient_case(size, seed, readnoise):
    img = make_background((size, size), seed, readnoise=readnoise)
    yy, xx = np.mgrid[0:size, 0:size]
    img += 30.0 * (xx + yy) / (2.0 * size)
    p0, p1 = _centreline(size, 45.0, 0.0)
    return img, p0, p1, {"kind": "gradient", "label": "ambiguous",
                         "readnoise": readnoise}


def _asymmetric_case(size, seed, amplitude, readnoise):
    # A genuinely asymmetric crest: two half-Gaussians with different sigma on
    # either side of the centreline (a symmetric ridge and a symmetric box both
    # leave a structured residual on one flank).
    img = make_background((size, size), seed, readnoise=readnoise)
    p0, p1 = _centreline(size, 45.0, 0.0)
    d = _signed_transverse_distance(img.shape, p0, p1)
    sig_left, sig_right = 1.0, 3.0
    prof = np.where(d <= 0,
                    amplitude * np.exp(-0.5 * (d / sig_left) ** 2),
                    amplitude * np.exp(-0.5 * (d / sig_right) ** 2))
    img += prof
    return img, p0, p1, {"kind": "asymmetric", "label": "ambiguous",
                         "amplitude": amplitude, "readnoise": readnoise}


# --------------------------------------------------------------------------- #
# Case registries (deterministic, small grids)
# --------------------------------------------------------------------------- #
def _build_dev_cases():
    cases = {}
    idx = 0
    angles = [0.0, 45.0, 90.0, 135.0]
    for si, sigma in enumerate([0.6, 0.8, 1.2, 1.5, 2.5, 3.5]):
        for ci, sub in enumerate([0.0, 0.25, 0.5, 0.75]):
            amp = AMPLITUDES[(si + ci) % len(AMPLITUDES)]
            rn = READNOISES[(si * 2 + ci) % len(READNOISES)]
            ang = angles[(si + ci) % len(angles)]
            cid = f"ridge_s{sigma}_c{sub}"
            cases[cid] = _ridge_case(192, DEV_SEED + idx, sigma, sub, ang, amp, rn)
            idx += 1
    for wi, width in enumerate([1, 2, 4, 6]):
        for bi, soft in enumerate([0.0, 0.5, 1.0, 2.0]):
            amp = AMPLITUDES[(wi + bi) % len(AMPLITUDES)]
            rn = READNOISES[(wi + bi) % len(READNOISES)]
            ang = 90.0 if (wi + bi) % 2 == 0 else 0.0
            cid = f"col_w{width}_b{soft}"
            cases[cid] = _column_case(192, DEV_SEED + idx, width, soft,
                                      0.25 * bi, ang, amp, rn)
            idx += 1
    cases["no_structure"] = _no_structure_case(192, DEV_SEED + idx, 3.0); idx += 1
    cases["double_ridge"] = _double_ridge_case(192, DEV_SEED + idx, 3.0, 300.0, 3.0); idx += 1
    cases["aligned_stars"] = _aligned_stars_case(192, DEV_SEED + idx, 300.0, 3.0); idx += 1
    cases["gradient"] = _gradient_case(192, DEV_SEED + idx, 3.0); idx += 1
    cases["asymmetric"] = _asymmetric_case(192, DEV_SEED + idx, 300.0, 3.0); idx += 1
    return cases


def _build_blind_cases():
    cases = {}
    idx = 0
    angles = [0.0, 45.0, 90.0, 135.0]
    for si, sigma in enumerate([0.7, 1.0, 1.8, 3.0]):
        for ci, sub in enumerate([0.125, 0.375, 0.625]):
            amp = AMPLITUDES[(si * 2 + ci + 1) % len(AMPLITUDES)]
            rn = READNOISES[(si + ci * 2 + 1) % len(READNOISES)]
            ang = angles[(si + ci + 1) % len(angles)]
            cid = f"ridge_s{sigma}_c{sub}"
            cases[cid] = _ridge_case(192, BLIND_SEED + idx, sigma, sub, ang, amp, rn)
            idx += 1
    for wi, width in enumerate([1.5, 3.0, 5.0]):
        for bi, soft in enumerate([0.25, 0.75, 1.5]):
            amp = AMPLITUDES[(wi + bi + 1) % len(AMPLITUDES)]
            rn = READNOISES[(wi + bi * 2 + 1) % len(READNOISES)]
            ang = 90.0 if (wi + bi) % 2 == 1 else 0.0
            cid = f"col_w{width}_b{soft}"
            cases[cid] = _column_case(192, BLIND_SEED + idx, width, soft,
                                      0.25 * (bi + 1), ang, amp, rn)
            idx += 1
    cases["no_structure"] = _no_structure_case(192, BLIND_SEED + idx, 4.0); idx += 1
    cases["double_ridge"] = _double_ridge_case(192, BLIND_SEED + idx, 2.5, 260.0, 4.0); idx += 1
    cases["aligned_stars"] = _aligned_stars_case(192, BLIND_SEED + idx, 260.0, 4.0); idx += 1
    cases["gradient"] = _gradient_case(192, BLIND_SEED + idx, 4.0); idx += 1
    cases["asymmetric"] = _asymmetric_case(192, BLIND_SEED + idx, 260.0, 4.0); idx += 1
    return cases


DEV_CASES = _build_dev_cases()
BLIND_CASES = _build_blind_cases()

SPLITS = {
    "dev": {"cases": DEV_CASES, "seed": DEV_SEED},
    "blind": {"cases": BLIND_CASES, "seed": BLIND_SEED},
}


def build_case(split, case_id, size=None):
    """Return ``(image, p0, p1, gt)`` for a profile-level case.

    ``size`` is ignored for the profile suite (cases are generated at 192 px;
    the transverse profile is resolution-independent in the discriminator), but
    kept for API symmetry with spike-002.
    """
    return SPLITS[split]["cases"][case_id]
