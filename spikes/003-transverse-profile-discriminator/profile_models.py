"""Transverse-profile shape discriminator (TRAIL-02C spike, mechanism only).

Built **only** on NumPy / SciPy already present in the repo venv.  No new
dependency, no production import, no file I/O.

The mechanism replaces the fragile ``tophat``/``step_sharpness`` shape gates of
TRAIL-02B (which fail at the nearest-centre sub-pixel of the centreline) with:

1. **Sub-pixel transverse sampling** — :func:`sample_transverse_profile_subpixel`
   samples the profile perpendicular to a candidate centreline with
   ``scipy.ndimage.map_coordinates(order=1)`` (bilinear), never ``round(x,y)``,
   and reduces over the longitudinal axis with a robust statistic (median).

2. **Explicit model comparison** — two bounded least-squares models are fitted
   to the same profile and compared on normalised quality (reduced RSS; AICc as
   a diagnostic when ``n`` is sufficient):
   * ``ridge``   — smooth Gaussian crest: ``baseline + A*exp(-0.5*((x-c)/s)^2)``
   * ``column``  — softened box plateau (difference of logistic sigmoids):
     ``baseline + A*(sigmoid((x-left)/soft) - sigmoid((x-right)/soft))``,
     with ``left/right = c +/- width/2``.

3. **Signed preference, never a probability** — the preference is a signed,
   symmetric normalised difference of reduced RSS in ``(-1, 1)``.  A three-way
   decision ``ridge | column | ambiguous`` is returned; ``ambiguous`` is a
   first-class, honest answer (insufficient delta, poor fit, or non-convergence),
   and non-convergence is **never** promoted to a default accept.

Coordinate conventions match spike 001/002 (``x`` = column, ``y`` = row, numpy
``[y, x]``).  A profile is a 1-D array indexed by *perpendicular offset* (px).
"""

from __future__ import annotations

import math
import warnings

import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares
from scipy.special import expit as _sigmoid


# --------------------------------------------------------------------------- #
# Frozen configuration (single source of truth; frozen BEFORE the blind run)
# --------------------------------------------------------------------------- #
CONFIG = {
    # sub-pixel transverse sampling
    "sample_order": 1,          # bilinear interpolation (map_coordinates order)
    "sample_half_width": 10.0,  # perpendicular half-span sampled (px)
    "sample_offset_step": 0.25, # offset resolution (px)
    "sample_long_reduce": "median",  # robust longitudinal reduction

    # model fitting
    "fit_max_nfev": 2000,
    "ridge_sigma_bounds": (0.3, 10.0),
    "column_width_bounds": (0.5, 20.0),
    "column_softness_bounds": (0.01, 4.0),

    # decision
    "min_snr": 4.0,             # peak/noise below this => ambiguous (no structure)
    "max_rss_frac": 0.10,       # best-model unexplained-variance fraction above this => ambiguous
    "pref_delta_threshold": 0.10,  # |preference| below this => ambiguous
    "aicc_delta_threshold": 4.0,   # |AICc delta| below this => ambiguous (strong-evidence bound)
    "column_flat_top_ratio": 2.0,  # column requires width > ratio*softness (resolvable flat top)
}


def default_offsets(cfg=CONFIG):
    """Return the symmetric perpendicular-offset grid (px) used for sampling."""
    hw = cfg["sample_half_width"]
    step = cfg["sample_offset_step"]
    return np.arange(-hw, hw + 0.5 * step, step)


# --------------------------------------------------------------------------- #
# Model functions (vectorised, params-first to match least_squares)
# --------------------------------------------------------------------------- #
def _ridge_fn(p, x):
    baseline, amplitude, center, sigma = p
    return baseline + amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def _column_fn(p, x):
    baseline, amplitude, center, width, softness = p
    left = center - width / 2.0
    right = center + width / 2.0
    s = max(softness, 1e-6)
    return baseline + amplitude * (_sigmoid((x - left) / s)
                                   - _sigmoid((x - right) / s))


RIDGE_PARAM_NAMES = ["baseline", "amplitude", "center", "sigma"]
COLUMN_PARAM_NAMES = ["baseline", "amplitude", "center", "width", "softness"]


# --------------------------------------------------------------------------- #
# Sub-pixel transverse sampling
# --------------------------------------------------------------------------- #
def sample_transverse_profile_subpixel(image_or_residual, p0, p1, offsets=None,
                                       n_long=None, cfg=CONFIG):
    """Sample the transverse profile perpendicular to ``p0 -> p1``, sub-pixel.

    Uses ``map_coordinates(order=1)`` (bilinear) at continuous coordinates — no
    ``round(x,y)``.  Reduces over the longitudinal axis with a robust statistic
    (median by default).  Returns ``(profile, coverage)`` where ``coverage`` is
    the fraction of sample points that fall inside the image.
    """
    img = np.asarray(image_or_residual, dtype=float)
    if img.ndim != 2:
        return np.zeros(0), 0.0
    H, W = img.shape
    if offsets is None:
        offsets = default_offsets(cfg)
    offsets = np.asarray(offsets, dtype=float)
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx, dy = x1 - x0, y1 - y0
    nrm = float(np.hypot(dx, dy))
    if nrm == 0:
        return np.zeros(len(offsets)), 0.0
    nx, ny = -dy / nrm, dx / nrm          # perpendicular unit vector
    if n_long is None:
        n_long = max(2, int(round(nrm)))
    t = np.linspace(0.0, 1.0, n_long)
    cx = x0 + dx * t
    cy = y0 + dy * t
    cols = cx[:, None] + nx * offsets[None, :]
    rows = cy[:, None] + ny * offsets[None, :]
    valid = (cols >= 0) & (cols <= W - 1) & (rows >= 0) & (rows <= H - 1)
    coverage = float(valid.mean())
    sampled = ndimage.map_coordinates(
        img, [rows.ravel(), cols.ravel()], order=cfg["sample_order"],
        mode="constant", cval=np.nan, prefilter=False)
    sampled = sampled.reshape(n_long, len(offsets))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if cfg["sample_long_reduce"] == "median":
            with np.errstate(invalid="ignore"):
                profile = np.nanmedian(sampled, axis=0)
        else:
            with np.errstate(invalid="ignore"):
                profile = np.nanmean(sampled, axis=0)
    profile = np.where(np.isfinite(profile), profile, 0.0)
    return profile, coverage


# --------------------------------------------------------------------------- #
# Fit helpers
# --------------------------------------------------------------------------- #
def _profile_noise(y):
    """Robust per-profile noise estimate (MAD about the median)."""
    med = float(np.median(y))
    mad = float(np.median(np.abs(y - med)))
    return 1.4826 * mad


def _fit_model(fn, x, y, p0, lower, upper, cfg=CONFIG):
    """Bounded least-squares fit; returns ``None`` on non-convergence."""
    try:
        res = least_squares(
            lambda p: fn(p, x) - y, p0, bounds=(lower, upper),
            method="trf", max_nfev=cfg["fit_max_nfev"],
            xtol=1e-10, ftol=1e-10, gtol=1e-10)
    except Exception:
        return None
    if res.status <= 0 or not np.all(np.isfinite(res.x)):
        return None
    rss = float(np.sum((fn(res.x, x) - y) ** 2))
    return {
        "params": np.asarray(res.x, dtype=float),
        "rss": rss,
        "n": len(x),
        "status": int(res.status),
        "success": bool(res.success),
        "optimality": float(res.optimality),
        "nfev": int(res.nfev),
    }


def _fit_best(fn, x, y, p0_list, lower, upper, cfg=CONFIG):
    """Try several initial guesses, keep the lowest-RSS converged fit."""
    best = None
    for p0 in p0_list:
        fit = _fit_model(fn, x, y, p0, lower, upper, cfg)
        if fit is None:
            continue
        if best is None or fit["rss"] < best["rss"]:
            best = fit
    return best


def _aicc(rss, n, k):
    """Akaike information criterion (corrected); ``None`` if n insufficient."""
    if n <= k + 1:
        return None
    if rss <= 0:
        rss = 1e-12
    return n * math.log(rss / n) + 2.0 * k + 2.0 * k * (k + 1) / (n - k - 1)


def _ambiguous(reason, **extra):
    out = {
        "label": "ambiguous",
        "reason": reason,
        "preference": 0.0,
        "aicc_delta": None,
        "snr": extra.get("snr"),
        "converged": extra.get("converged", False),
    }
    out.update({k: v for k, v in extra.items()
                if k not in out or out[k] is None})
    return out


# --------------------------------------------------------------------------- #
# Discriminator
# --------------------------------------------------------------------------- #
def discriminate_profile(profile, offsets=None, noise=None, cfg=CONFIG):
    """Classify a 1-D transverse profile as ``ridge`` / ``column`` / ``ambiguous``.

    Returns a dict with ``label``, a signed ``preference`` in ``(-1, 1)``
    (positive => ridge preferred), ``snr``, ``converged``, per-model fit
    diagnostics, ``aicc_delta`` (positive => ridge preferred) and ``reason``.
    Non-convergence of *either* model yields ``ambiguous`` (fail-safe).
    """
    y = np.asarray(profile, dtype=float)
    if offsets is None:
        offsets = np.arange(len(y), dtype=float) - (len(y) - 1) / 2.0
    x = np.asarray(offsets, dtype=float)

    if y.size < 8 or not np.all(np.isfinite(y)):
        return _ambiguous("profile too short or non-finite", converged=False)

    span = float(y.max() - y.min())
    if span <= 0:
        return _ambiguous("flat profile", snr=0.0, converged=False)

    noise_est = noise if noise is not None else _profile_noise(y)
    noise_est = max(noise_est, 1e-9)

    peak_idx = int(np.argmax(y))
    xpeak = float(x[peak_idx])
    baseline0 = float(np.min(y))
    amp0 = max(span, 1e-3)

    ridge_lo = (-np.inf, 0.0, x[0] - cfg["sample_half_width"],
                cfg["ridge_sigma_bounds"][0])
    ridge_hi = (np.inf, np.inf, x[-1] + cfg["sample_half_width"],
                cfg["ridge_sigma_bounds"][1])
    col_lo = (-np.inf, 0.0, x[0] - cfg["sample_half_width"],
              cfg["column_width_bounds"][0], cfg["column_softness_bounds"][0])
    col_hi = (np.inf, np.inf, x[-1] + cfg["sample_half_width"],
              cfg["column_width_bounds"][1], cfg["column_softness_bounds"][1])

    # multiple initial guesses per model (robustness to local minima)
    ridge_inits = [
        [baseline0, amp0, xpeak, 1.5],
        [baseline0, amp0, xpeak, 0.8],
        [baseline0, amp0, xpeak, 3.0],
    ]
    col_inits = [
        [baseline0, amp0, xpeak, 2.0, 0.5],
        [baseline0, amp0, xpeak, 4.0, 0.5],
        [baseline0, amp0, xpeak, 2.0, 1.0],
    ]
    ridge = _fit_best(_ridge_fn, x, y, ridge_inits, ridge_lo, ridge_hi, cfg)
    column = _fit_best(_column_fn, x, y, col_inits, col_lo, col_hi, cfg)

    if ridge is None or column is None:
        return _ambiguous("non-convergence", snr=amp0 / noise_est,
                          converged=False)

    a_r = float(ridge["params"][1])
    a_c = float(column["params"][1])
    a_best = max(a_r, a_c, 1e-12)
    snr = a_best / noise_est

    if snr < cfg["min_snr"]:
        return _ambiguous("no structure (low SNR)", snr=snr,
                          converged=True)

    rms_r = math.sqrt(ridge["rss"] / ridge["n"])
    rms_c = math.sqrt(column["rss"] / column["n"])
    rss_best = min(ridge["rss"], column["rss"])
    sstot = float(np.sum((y - np.mean(y)) ** 2))
    rss_frac = rss_best / sstot if sstot > 0 else 1.0
    if rss_frac > cfg["max_rss_frac"]:
        return _ambiguous("poor fit (structured residual)", snr=snr,
                          converged=True)

    dof_r = ridge["n"] - 4
    dof_c = column["n"] - 5
    rrss_r = ridge["rss"] / max(dof_r, 1)
    rrss_c = column["rss"] / max(dof_c, 1)
    pref = (rrss_c - rrss_r) / max(rrss_r + rrss_c, 1e-12)

    aicc_r = _aicc(ridge["rss"], ridge["n"], 4)
    aicc_c = _aicc(column["rss"], column["n"], 5)
    aicc_delta = (aicc_c - aicc_r) if (aicc_r is not None and aicc_c is not None) else None

    # Physical flat-top check: a "column" classification is only valid if the
    # fitted plateau actually has a resolvable flat top (width > ratio*softness).
    # A degenerate "column" fit (tiny width pinned at the lower bound, soft
    # edges) is just a smooth bump approximating a ridge, so it must NOT be
    # promoted to a confident "column".
    col_w = float(column["params"][3])
    col_s = float(column["params"][4])
    plateau_valid = col_w > cfg["column_flat_top_ratio"] * col_s

    # Decision: AICc delta is the primary signal (penalises the extra column
    # parameter, which lets it approximate a Gaussian ridge); reduced-RSS
    # preference is the fallback when n is too small for AICc.
    if aicc_delta is not None:
        if abs(aicc_delta) < cfg["aicc_delta_threshold"]:
            label = "ambiguous"
            reason = "insufficient AICc delta"
        elif aicc_delta > 0:
            label = "ridge"
            reason = "ridge preferred (AICc)"
        else:
            if plateau_valid:
                label = "column"
                reason = "column preferred (AICc)"
            else:
                label = "ambiguous"
                reason = "column fit degenerate (no flat top)"
    else:
        if abs(pref) < cfg["pref_delta_threshold"]:
            label = "ambiguous"
            reason = "insufficient delta"
        elif pref > 0:
            label = "ridge"
            reason = "ridge preferred"
        else:
            if plateau_valid:
                label = "column"
                reason = "column preferred"
            else:
                label = "ambiguous"
                reason = "column fit degenerate (no flat top)"

    return {
        "label": label,
        "reason": reason,
        "preference": float(pref),
        "snr": snr,
        "converged": True,
        "aicc_delta": aicc_delta,
        "ridge": {
            "params": {k: float(v) for k, v in zip(RIDGE_PARAM_NAMES, ridge["params"])},
            "rss": ridge["rss"], "rrss": rrss_r, "aicc": aicc_r,
            "status": ridge["status"], "nfev": ridge["nfev"],
        },
        "column": {
            "params": {k: float(v) for k, v in zip(COLUMN_PARAM_NAMES, column["params"])},
            "rss": column["rss"], "rrss": rrss_c, "aicc": aicc_c,
            "status": column["status"], "nfev": column["nfev"],
        },
    }
