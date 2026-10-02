"""Adaptive Hough trail detector (TRAIL-02B spike, custom backend).

Built **only** on NumPy / SciPy / scikit-image already present in the repo
venv.  No new dependency, no production import, no file I/O.

Pipeline (five separable, logged stages)
----------------------------------------
1. Robust background + noise: median-filter low-frequency background
   subtraction, noise scale via MAD.
2. Multi-scale edge candidates: Canny on a noise-normalised (SNR) residual at
   two explicit smoothing scales, then ``probabilistic_hough_line`` with a
   ``theta`` grid covering **all** angles (0..179 deg, i.e. including the 0/90
   axis orientations).
3. Collinear segment grouping: segments are clustered by (orientation angle +
   perpendicular offset ``rho`` + longitudinal gap) into straight *lines*;
   parallel nearby lines are then merged into *trail* candidates, keeping
   full-resolution endpoints.  Segments are never counted as trails.
4. Interpretable validation, one component per feature (logged separately):
   transverse contrast, width/profile, continuity, longitudinal support, and
   a top-hat/boxiness shape measure.  A composite ``score`` is reported; it is
   a score, never a probability.
5. Measurement-based artefact rejection: a boxy (top-hat) transverse profile —
   the signature of a hot-column defect — is rejected on the shape measurement,
   not by blanket-excluding vertical/horizontal orientations.

Coordinate conventions match spike 001 (``x`` = column, ``y`` = row, numpy
``[y, x]``; ``angle_deg`` = ``atan2(dy, dx)`` folded to [0, 180)).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.feature import canny
from skimage.transform import probabilistic_hough_line


# --------------------------------------------------------------------------- #
# Frozen configuration (single source of truth; frozen after the DEV attempts)
# --------------------------------------------------------------------------- #
CONFIG = {
    # Stage 1 — background / noise
    "bg_filter": "median",      # low-frequency background estimate
    "bg_size_frac": 0.13,       # median filter size = max(15, round(size*frac)) (odd)
    "noise_method": "mad",      # robust sigma = 1.4826 * MAD of residual

    # Stage 2 — multi-scale edges
    "canny_scales": [1.0, 2.5],   # two explicit Gaussian smoothing scales (px)
    "canny_low": 2.0,             # low hysteresis threshold (SNR gradient units)
    "canny_high": 4.0,            # high hysteresis threshold (SNR gradient units)
    "theta_step_deg": 1.0,        # angular grid step; theta = 0..179 deg (all angles)
    "hough_threshold_frac": 0.20, # min Hough votes = max(12, round(size*frac))
    "hough_line_length_frac": 0.30,  # min accepted segment length (px)
    "hough_line_gap_frac": 0.08,  # max gap merged inside a segment (px)

    # Stage 3 — grouping
    "group_angle_tol_deg": 3.0,   # collinearity angle tolerance
    "group_rho_tol": 1.0,         # collinearity perpendicular-offset tolerance (px)
    "trail_angle_tol_deg": 3.0,   # trail (parallel lines) angle tolerance
    "trail_max_width": 8.0,       # max perpendicular spread to merge parallel lines (px)
    "trail_overlap_frac": 0.15,   # min longitudinal overlap to merge two lines

    # Stage 4/5 — validation thresholds (per feature)
    "min_contrast_snr": 6.0,      # transverse peak / noise
    "min_continuity": 0.70,       # fraction of the ridge above 0.5*peak
    "min_width": 1.0,             # FWHM lower bound (px)
    "max_width": 9.0,             # FWHM upper bound (px)
    "max_step_sharpness": 0.65,   # max |2nd diff|/peak > this => hard step (hard column)
    "max_tophat": 0.30,           # width@0.9/width@0.1 > this => flat top (soft column)
    "min_length_frac": 0.30,      # min longitudinal length = size*frac (px)

    # Composite score weights (sum to 1); score in [0,1], never a probability
    "w_contrast": 0.30,
    "w_continuity": 0.25,
    "w_width": 0.15,
    "w_shape": 0.20,
    "w_support": 0.10,
    "score_ref_contrast_snr": 20.0,
    "score_ref_continuity": 0.8,
    "score_ref_support": 1.0,     # support_score = clip(length / (size*ref), 0, 1)
}


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def angle_from_endpoints(p0, p1):
    """Physical orientation in [0, 180) degrees from two ``(x, y)`` points."""
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    return float(np.degrees(np.arctan2(dy, dx))) % 180.0


def angular_distance_deg(a, b):
    d = abs((a % 180.0) - (b % 180.0)) % 180.0
    return min(d, 180.0 - d)


def circular_mean_angle(angles):
    """Circular mean of orientations in [0, 180) (modulo 180, double-angle).

    ``179`` and ``1`` are 2 deg apart in orientation space but 178 deg apart as
    plain numbers; a plain mean gives 90 deg (wrong).  The double-angle trick
    maps the 180-degree periodicity to a full circle, so the circular mean of
    ``[179, 1]`` is ~0 deg.  Returns a value in [0, 180).
    """
    ang = np.asarray(angles, dtype=float)
    if ang.size == 0:
        return 0.0
    two = 2.0 * np.radians(ang)
    mx = float(np.mean(np.cos(two)))
    my = float(np.mean(np.sin(two)))
    result = float(np.degrees(np.arctan2(my, mx)) / 2.0) % 180.0
    if result >= 180.0 - 1e-9:   # snap the 0/180 boundary (float noise)
        result = 0.0
    return result


def line_params(p0, p1):
    """Return ``(phi, theta, rho)`` for the infinite line through two points.

    ``phi`` is the physical orientation in [0, 180).  ``theta`` is the normal
    angle ``(phi + 90) % 180`` and ``rho`` the signed perpendicular distance
    from the origin, so a line and its reverse map to the same ``(theta, rho)``.
    """
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    phi = float(np.degrees(np.arctan2(dy, dx))) % 180.0
    theta = (phi + 90.0) % 180.0
    tr = np.radians(theta)
    rho = float(p0[0]) * np.cos(tr) + float(p0[1]) * np.sin(tr)
    return phi, theta, rho


def _project_extent(points, phi, rho):
    """Merge a set of (x, y) points into a full-resolution line extent.

    Projects each point onto the infinite line of orientation ``phi`` and
    perpendicular offset ``rho`` (using the *same* normal convention as
    :func:`line_params`), so the merged endpoints keep their offset.
    Returns ``(p0, p1, length)``.
    """
    rad = np.radians(phi)
    ux, uy = np.cos(rad), np.sin(rad)          # direction unit vector
    theta = (phi + 90.0) % 180.0
    tr = np.radians(theta)
    nx, ny = np.cos(tr), np.sin(tr)            # normal unit vector (matches line_params)
    ox, oy = rho * nx, rho * ny                # point on the line closest to origin
    ts = [float(px - ox) * ux + float(py - oy) * uy for (px, py) in points]
    t0, t1 = min(ts), max(ts)
    p0 = (ox + t0 * ux, oy + t0 * uy)
    p1 = (ox + t1 * ux, oy + t1 * uy)
    length = t1 - t0
    return p0, p1, length


# --------------------------------------------------------------------------- #
# Stage 1 — background / noise
# --------------------------------------------------------------------------- #
def preprocess(image, cfg=CONFIG):
    """Return ``(residual, noise)``: background-subtracted image + robust sigma.

    Background = median filter (low-frequency, robust to thin trails/stars);
    noise = 1.4826 * MAD of the residual (robust to the trail itself).
    """
    arr = np.asarray(image, dtype=float)
    size = max(arr.shape)
    bsize = max(15, int(round(size * cfg["bg_size_frac"])))
    bsize = bsize if bsize % 2 == 1 else bsize + 1
    bg = ndimage.median_filter(arr, size=bsize)
    residual = arr - bg
    med = float(np.median(residual))
    mad = float(np.median(np.abs(residual - med)))
    noise = 1.4826 * mad
    noise = max(noise, 1e-6)
    return residual, noise


# --------------------------------------------------------------------------- #
# Stage 2 — multi-scale edge candidates
# --------------------------------------------------------------------------- #
def edge_segments(residual, noise, size, seed, cfg=CONFIG):
    """Canny (two scales) + probabilistic Hough, theta over all angles.

    Returns a list of ``((x0, y0), (x1, y1))`` segments (union of both scales).
    """
    snr = residual / noise
    threshold = max(12, int(round(size * cfg["hough_threshold_frac"])))
    line_length = max(12, int(round(size * cfg["hough_line_length_frac"])))
    line_gap = max(4, int(round(size * cfg["hough_line_gap_frac"])))
    theta = np.deg2rad(np.arange(0.0, 180.0, cfg["theta_step_deg"]))

    segs = []
    for scale in cfg["canny_scales"]:
        edges = canny(snr, sigma=scale,
                      low_threshold=cfg["canny_low"],
                      high_threshold=cfg["canny_high"])
        found = probabilistic_hough_line(
            edges, threshold=threshold, line_length=line_length,
            line_gap=line_gap, theta=theta, rng=int(seed))
        segs.extend(found)
    return segs


# --------------------------------------------------------------------------- #
# Stage 3 — grouping (collinear lines, then parallel lines -> trails)
# --------------------------------------------------------------------------- #
def group_into_lines(segments, cfg=CONFIG):
    """Cluster collinear segments into straight *lines* (bounded, complete-link).

    Greedy **complete-link** clustering: a segment joins a cluster only if it is
    within the angle AND rho tolerances of **every** member already in that
    cluster.  This guarantees, for every resulting line, that the maximum
    pairwise angular distance is <= ``group_angle_tol_deg`` and that
    ``max(rho) - min(rho) <= group_rho_tol`` (no transitive single-link chain
    bridging, e.g. rho 0 / 0.8 / 1.6 no longer form one cluster of spread 1.6).
    """
    items = []
    for (p0, p1) in segments:
        phi, theta, rho = line_params(p0, p1)
        items.append({"p0": p0, "p1": p1, "phi": phi, "rho": rho,
                      "pts": [p0, p1]})

    a_tol = cfg["group_angle_tol_deg"]
    r_tol = cfg["group_rho_tol"]
    n = len(items)

    clusters = []
    for i in range(n):
        placed = False
        for cl in clusters:
            ok = all(
                angular_distance_deg(items[i]["phi"], items[j]["phi"]) <= a_tol
                and abs(items[i]["rho"] - items[j]["rho"]) <= r_tol
                for j in cl)
            if ok:
                cl.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    lines = []
    for cl in clusters:
        members = [items[j] for j in cl]
        phi = circular_mean_angle([m["phi"] for m in members])
        rho = float(np.mean([m["rho"] for m in members]))
        pts = [pt for m in members for pt in m["pts"]]
        p0, p1, length = _project_extent(pts, phi, rho)
        lines.append({
            "phi": phi, "rho": rho, "p0": p0, "p1": p1,
            "length": length, "n_segments": len(members),
        })
    return lines


def _overlap_frac(li, lj):
    """Longitudinal overlap fraction between two lines (0..1)."""
    p0i, p1i, _ = _project_extent([li["p0"], li["p1"]], li["phi"], li["rho"])
    p0j, p1j, _ = _project_extent([lj["p0"], lj["p1"]], lj["phi"], lj["rho"])
    rad = np.radians(li["phi"])
    ux, uy = np.cos(rad), np.sin(rad)
    ti0, ti1 = (p0i[0] * ux + p0i[1] * uy, p1i[0] * ux + p1i[1] * uy)
    tj0, tj1 = (p0j[0] * ux + p0j[1] * uy, p1j[0] * ux + p1j[1] * uy)
    span_i = abs(ti1 - ti0)
    span_j = abs(tj1 - tj0)
    if span_i <= 0 or span_j <= 0:
        return 0.0
    overlap = (min(max(ti0, ti1), max(tj0, tj1))
               - max(min(ti0, ti1), min(tj0, tj1)))
    return overlap / min(span_i, span_j)


def _lines_compatible(li, lj, a_tol, max_w, ov_frac):
    if angular_distance_deg(li["phi"], lj["phi"]) > a_tol:
        return False
    if abs(li["rho"] - lj["rho"]) > max_w:
        return False
    return _overlap_frac(li, lj) >= ov_frac


def group_into_trails(lines, cfg=CONFIG):
    """Merge parallel, longitudinally overlapping lines into physical trails.

    Bounded **complete-link** clustering: a line joins a cluster only if it is
    compatible (angle <= ``trail_angle_tol_deg``, perpendicular spread
    <= ``trail_max_width``, overlap >= ``trail_overlap_frac``) with **every**
    member already in the cluster.  This guarantees ``max(rho) - min(rho)
    <= trail_max_width`` and maximum pairwise angular distance <= the angle
    tolerance (no rho chain 0 / 7 / 14 bridging into one cluster of spread 14).
    """
    a_tol = cfg["trail_angle_tol_deg"]
    max_w = cfg["trail_max_width"]
    ov_frac = cfg["trail_overlap_frac"]
    n = len(lines)

    clusters = []
    for i in range(n):
        placed = False
        for cl in clusters:
            if all(_lines_compatible(lines[i], lines[j], a_tol, max_w, ov_frac)
                   for j in cl):
                cl.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    trails = []
    for cl in clusters:
        members = [lines[j] for j in cl]
        phi = circular_mean_angle([m["phi"] for m in members])
        rhos = [m["rho"] for m in members]
        rho = float(np.mean(rhos))
        pts = [pt for m in members for pt in [m["p0"], m["p1"]]]
        p0, p1, length = _project_extent(pts, phi, rho)
        trails.append({
            "phi": phi, "rho": rho, "p0": p0, "p1": p1,
            "length": length, "n_lines": len(members),
            "n_segments": sum(m["n_segments"] for m in members),
            "rho_spread": float(max(rhos) - min(rhos)),
        })
    return trails


# --------------------------------------------------------------------------- #
# Stage 4 — measurement + validation
# --------------------------------------------------------------------------- #
def transverse_profile(residual, p0, p1, W=8, n_long=None):
    """Mean residual profile sampled perpendicular to the segment ``p0->p1``.

    Returns a length ``2*W+1`` array (offset ``-W..W`` in px), averaged over the
    longitudinal samples that stay fully in-bounds.
    """
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx, dy = x1 - x0, y1 - y0
    nrm = float(np.hypot(dx, dy))
    if nrm == 0:
        return np.zeros(2 * W + 1)
    nx, ny = -dy / nrm, dx / nrm
    H, Ww = residual.shape
    n_long = n_long if n_long is not None else max(2, int(round(nrm)))
    acc = np.zeros(2 * W + 1)
    cnt = 0
    for t in np.linspace(0.0, 1.0, n_long):
        cx = x0 + dx * t
        cy = y0 + dy * t
        vals = []
        for k in range(-W, W + 1):
            px = int(round(cx + nx * k))
            py = int(round(cy + ny * k))
            if 0 <= px < Ww and 0 <= py < H:
                vals.append(residual[py, px])
            else:
                vals.append(np.nan)
        vals = np.array(vals)
        if np.isnan(vals).any():
            continue
        acc += vals
        cnt += 1
    if cnt == 0:
        return np.zeros(2 * W + 1)
    return acc / cnt


def _longitudinal_profile(residual, p0, p1, n_long=None):
    """Residual sampled along the centreline (for continuity)."""
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx, dy = x1 - x0, y1 - y0
    nrm = float(np.hypot(dx, dy))
    if nrm == 0:
        return np.zeros(1)
    H, Ww = residual.shape
    n_long = n_long if n_long is not None else max(2, int(round(nrm)))
    out = []
    for t in np.linspace(0.0, 1.0, n_long):
        px = int(round(x0 + dx * t))
        py = int(round(y0 + dy * t))
        if 0 <= px < Ww and 0 <= py < H:
            out.append(residual[py, px])
    return np.array(out)


def measure_and_validate(residual, noise, trail, size, cfg=CONFIG):
    """Compute interpretable features, component scores and accept/reject.

    Returns a trail dict enriched with ``features``, ``component_scores``,
    ``score``, ``accepted`` and ``reasons``.  Rejection is always grounded in a
    measured feature (never an orientation shortcut).
    """
    W = 8
    prof = transverse_profile(residual, trail["p0"], trail["p1"], W=W)
    long_prof = _longitudinal_profile(residual, trail["p0"], trail["p1"])

    peak = float(prof.max())
    contrast_snr = peak / noise

    # width (FWHM) in profile bins (1 px each)
    half = 0.5 * peak
    width_fwhm = float(np.count_nonzero(prof >= half))

    # continuity: fraction of longitudinal samples above 0.5 * peak
    if len(long_prof) and peak > 0:
        continuity = float(np.mean(long_prof >= 0.5 * peak))
    else:
        continuity = 0.0

    # top-hat / boxiness: width@0.9*peak / width@0.1*peak (1 px bins).
    # A Gaussian ridge has a small value (~0.1-0.3); a hard column plateau has
    # ~1.0 and a soft 4-px column plateau ~0.5.  This is the flat-top gate (the
    # hard-step gate is step_sharpness below).
    w90 = np.count_nonzero(prof >= 0.9 * peak) if peak > 0 else 0
    w10 = np.count_nonzero(prof >= 0.1 * peak) if peak > 0 else 0
    tophat = float(w90 / w10) if w10 > 0 else 1.0

    # edge hardness: max absolute first difference / peak (informative).
    if peak > 0 and len(prof) > 1:
        edge_hardness = float(np.max(np.abs(np.diff(prof))) / peak)
    else:
        edge_hardness = 0.0

    # step sharpness: max absolute SECOND difference / peak.  Robust to the
    # sub-pixel sampling of a hard step: a rectangular column edge produces a
    # second-difference spike ~ the full step height (~1.0 after normalisation),
    # while a smooth Gaussian ridge has bounded curvature (~1/sigma^2, ~0.4 for
    # sigma=1.5 px).  This is the hard-step column gate (soft columns are caught
    # by the flat-top ``tophat`` gate).
    if peak > 0 and len(prof) > 2:
        second = np.diff(np.diff(prof))
        step_sharpness = float(np.max(np.abs(second)) / peak)
    else:
        step_sharpness = 0.0

    length = float(trail["length"])
    features = {
        "contrast_snr": contrast_snr,
        "width_fwhm": width_fwhm,
        "continuity": continuity,
        "tophat": tophat,
        "edge_hardness": edge_hardness,
        "step_sharpness": step_sharpness,
        "length": length,
        "n_lines": int(trail["n_lines"]),
        "n_segments": int(trail["n_segments"]),
    }

    # Component scores (each in [0, 1]); score is a score, never a probability.
    c_contrast = float(np.clip(contrast_snr / cfg["score_ref_contrast_snr"], 0, 1))
    c_continuity = float(np.clip(continuity / cfg["score_ref_continuity"], 0, 1))
    w_min, w_max = cfg["min_width"], cfg["max_width"]
    if w_min <= width_fwhm <= w_max:
        c_width = 1.0
    else:
        c_width = max(0.0, 1.0 - min(abs(width_fwhm - w_min),
                                     abs(width_fwhm - w_max)) / 5.0)
    # shape score: worst of the two column shape signatures (hard step, flat top)
    shape_violation = max(step_sharpness / 0.65, tophat / 0.40)
    c_shape = float(np.clip(1.0 - shape_violation, 0, 1))
    support_ref = size * cfg["score_ref_support"]
    c_support = float(np.clip(length / support_ref, 0, 1))

    score = (cfg["w_contrast"] * c_contrast
             + cfg["w_continuity"] * c_continuity
             + cfg["w_width"] * c_width
             + cfg["w_shape"] * c_shape
             + cfg["w_support"] * c_support)
    score = float(np.clip(score, 0.0, 1.0))

    # Hard accept/reject gates (each grounded in a measured feature).
    reasons = []
    if contrast_snr < cfg["min_contrast_snr"]:
        reasons.append(f"contrast {contrast_snr:.1f} < {cfg['min_contrast_snr']:.1f}")
    if continuity < cfg["min_continuity"]:
        reasons.append(f"continuity {continuity:.2f} < {cfg['min_continuity']:.2f}")
    if not (w_min <= width_fwhm <= w_max):
        reasons.append(f"width {width_fwhm:.1f} outside [{w_min},{w_max}]")
    if step_sharpness > cfg["max_step_sharpness"]:
        reasons.append(
            f"step_sharpness {step_sharpness:.2f} > {cfg['max_step_sharpness']:.2f} "
            "(hard step / hard column)")
    if tophat > cfg["max_tophat"]:
        reasons.append(
            f"tophat {tophat:.2f} > {cfg['max_tophat']:.2f} (flat top / soft column)")
    if length < size * cfg["min_length_frac"]:
        reasons.append(f"length {length:.0f} < {size * cfg['min_length_frac']:.0f}")

    accepted = len(reasons) == 0

    trail = dict(trail)
    trail.update({
        "features": features,
        "component_scores": {
            "contrast": c_contrast,
            "continuity": c_continuity,
            "width": c_width,
            "shape": c_shape,
            "support": c_support,
        },
        "score": score,
        "accepted": accepted,
        "reasons": reasons,
    })
    return trail


# --------------------------------------------------------------------------- #
# Top-level entry point
# --------------------------------------------------------------------------- #
def detect(image, size, seed, cfg=CONFIG):
    """Full pipeline on a 2D image.

    Returns ``{"state": "ok", "n_segments": int, "n_lines": int, "trails": [...],
    "segments": [...], "lines": [...], "noise": float}`` where ``trails`` holds
    accepted+rejected trail candidates (with features/scores), ``segments`` the
    initial Hough segments (bounded) and ``lines`` the grouped collinear lines.
    """
    try:
        arr = np.asarray(image)
        if arr.size == 0 or arr.ndim != 2:
            return {
                "state": "error",
                "error": "image must be a non-empty 2D array",
                "noise": None, "n_segments": None, "n_lines": None,
                "n_trails": None, "n_accepted": None,
                "segments": [], "lines": [], "trails": [],
            }
        residual, noise = preprocess(arr, cfg)
        segments = edge_segments(residual, noise, size, seed, cfg)
        lines = group_into_lines(segments, cfg)
        trails_raw = group_into_trails(lines, cfg)
        trails = [measure_and_validate(residual, noise, t, size, cfg)
                  for t in trails_raw]

        # Bounded raw outputs: coordinates only, no pixel dumps.
        segs_out = [{"p0": [float(s[0][0]), float(s[0][1])],
                     "p1": [float(s[1][0]), float(s[1][1])]} for s in segments]
        lines_out = [{"phi": round(l["phi"], 2), "rho": round(l["rho"], 2),
                      "p0": [float(l["p0"][0]), float(l["p0"][1])],
                      "p1": [float(l["p1"][0]), float(l["p1"][1])],
                      "length": round(l["length"], 1),
                      "n_segments": int(l["n_segments"])} for l in lines]

        return {
            "state": "ok",
            "noise": float(noise),
            "n_segments": len(segments),
            "n_lines": len(lines),
            "n_trails": len(trails),
            "n_accepted": sum(1 for t in trails if t["accepted"]),
            "segments": segs_out,
            "lines": lines_out,
            "trails": trails,
        }
    except Exception as exc:  # pragma: no cover - fail-safe path
        return {
            "state": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "noise": None,
            "n_segments": None,
            "n_lines": None,
            "n_trails": None,
            "n_accepted": None,
            "segments": [],
            "lines": [],
            "trails": [],
        }
