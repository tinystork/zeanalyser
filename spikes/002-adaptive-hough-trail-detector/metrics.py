"""Assessment + aggregation for the adaptive-Hough spike (TRAIL-02B).

All metrics are explicitly **synthetic** (deterministic synthetic corpus only):
they are not product recall/precision, and no product threshold is derived.

Localisation is reported where possible and is **bounded**: a ground-truth trail
only counts as *matched* when a detected trail is within both an angle and an
offset tolerance (see :data:`MATCH_ANGLE_TOL_DEG` / :data:`MATCH_OFFSET_TOL_PX`),
so an unrelated line can never be claimed as a localisation match.  Grouping is
reported as the physical trail count (``n_trails``) — segments are never counted
as trails — plus the per-positive ``physical_trail_rate`` (matched / GT trails)
and a ``grouping_coherent`` flag (all GT trails matched AND no accepted extras).

A technical failure (``state != "ok"``) is never a FN/TN: only ``state == "ok"``
rows feed the synthetic TP/FP/FN/TN counts; non-ok rows are reported separately.
"""

from __future__ import annotations

import numpy as np

# Bounded localisation matching (evidence: measured angle error ~0.07 deg and
# offset error <~1 px on DEV/observed; 3 deg / 5 px are generous but bounded).
MATCH_ANGLE_TOL_DEG = 3.0
MATCH_OFFSET_TOL_PX = 5.0


def angular_distance_deg(a, b):
    d = abs((a % 180.0) - (b % 180.0)) % 180.0
    return min(d, 180.0 - d)


def _gt_line_params(gt_trail):
    from detector import line_params
    return line_params(gt_trail["p0"], gt_trail["p1"])


def _endpoint_error(gt_trail, det_trail):
    gp0, gp1 = np.array(gt_trail["p0"], float), np.array(gt_trail["p1"], float)
    dp0, dp1 = np.array(det_trail["p0"], float), np.array(det_trail["p1"], float)
    d1 = (np.linalg.norm(gp0 - dp0) + np.linalg.norm(gp1 - dp1)) / 2.0
    d2 = (np.linalg.norm(gp0 - dp1) + np.linalg.norm(gp1 - dp0)) / 2.0
    return float(min(d1, d2))


def match_trails(gt, accepted_trails,
                 angle_tol=MATCH_ANGLE_TOL_DEG, offset_tol=MATCH_OFFSET_TOL_PX):
    """Greedily match each GT trail to an accepted detected trail, **bounded**.

    A GT trail is matched only if some detected trail is within *both* the
    angle and the offset tolerance; otherwise it is reported as missed.  Returns
    ``(matches, unmatched)`` where each match has ``matched`` True/False and the
    detected error fields, and ``unmatched`` lists accepted extras.
    """
    n_gt = len(gt["gt_trails"])
    if n_gt == 0:
        return [], list(accepted_trails)

    used = [False] * len(accepted_trails)
    matches = []
    for g in gt["gt_trails"]:
        gphi, _, grho = _gt_line_params(g)
        best = None
        best_cost = None
        for j, d in enumerate(accepted_trails):
            if used[j]:
                continue
            ad = angular_distance_deg(gphi, d["phi"])
            off = abs(grho - d["rho"])
            if ad > angle_tol or off > offset_tol:
                continue  # outside tolerance => not a valid match
            cost = ad + off
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = j
        if best is not None:
            used[best] = True
            d = accepted_trails[best]
            matches.append({
                "gt_label": g["label"],
                "matched": True,
                "angle_error_deg": angular_distance_deg(gphi, d["phi"]),
                "offset_error_px": abs(grho - d["rho"]),
                "endpoint_error_px": _endpoint_error(g, d),
                "detected_angle_deg": round(d["phi"], 2),
                "detected_score": round(d["score"], 3),
            })
        else:
            matches.append({"gt_label": g["label"], "matched": False})
    unmatched = [d for j, d in enumerate(accepted_trails) if not used[j]]
    return matches, unmatched


def assess_case(gt, result):
    """Attach synthetic per-case metrics to a detector result.

    ``result`` is the detector output enriched with ``case_id``/``split`` by the
    runner.  ``detected`` here = ``n_accepted > 0`` (accepted physical trails).
    """
    out = dict(result)
    out["gt_has_trail"] = bool(gt["gt_has_trail"])
    out["gt_ntrails"] = len(gt["gt_trails"])

    ok = result.get("state") == "ok"
    n_accepted = result.get("n_accepted") or 0
    n_trails = result.get("n_trails") or 0

    out["angle_error_deg"] = None
    out["offset_error_px"] = None
    out["endpoint_error_px"] = None
    out["n_matched"] = None
    out["n_missed"] = None
    out["n_extra"] = None
    out["physical_trail_rate"] = None
    out["grouping_coherent"] = None

    if not ok:
        out["is_true_positive"] = None
        out["is_false_positive"] = None
        return out

    accepted_trails = [t for t in (result.get("trails") or []) if t.get("accepted")]
    if gt["gt_has_trail"]:
        matches, unmatched = match_trails(gt, accepted_trails)
        n_gt = len(gt["gt_trails"])
        n_matched = sum(1 for m in matches if m.get("matched"))
        n_extra = len(unmatched)
        out["n_matched"] = n_matched
        out["n_missed"] = n_gt - n_matched
        out["n_extra"] = n_extra
        out["physical_trail_rate"] = (n_matched / n_gt) if n_gt else None
        out["grouping_coherent"] = bool(n_gt > 0 and n_matched == n_gt
                                        and n_extra == 0)
        out["trail_matches"] = matches
        # Image-level TP is now **geometrically matched**: at least one GT trail
        # strictly within the angle+rho tolerances.  A positive whose accepted
        # trails are all out of tolerance is a FN image (with extras), never a
        # TP via a mere ``n_accepted > 0``.  (Standard image metric = at least
        # one matched; completeness via physical_trail_rate / grouping_coherent.)
        out["is_true_positive"] = bool(n_matched >= 1)
        out["is_false_positive"] = False
        ok_matches = [m for m in matches if m.get("matched")]
        if ok_matches:
            out["angle_error_deg"] = ok_matches[0]["angle_error_deg"]
            out["offset_error_px"] = ok_matches[0]["offset_error_px"]
            out["endpoint_error_px"] = ok_matches[0]["endpoint_error_px"]
    else:
        out["n_matched"] = 0
        out["n_missed"] = 0
        out["n_extra"] = n_accepted
        out["physical_trail_rate"] = None
        out["grouping_coherent"] = None
        # negative case: any accepted trail => FP
        out["is_true_positive"] = False
        out["is_false_positive"] = bool(n_accepted > 0)
    return out


def assess_backend_case(gt, result):
    """Assess a public spike-001 backend result for the coarse comparison.

    Unlike :func:`assess_case`, this reads the backend's own ``detected``
    boolean (satdet has ``n_accepted is None`` but a real ``detected``), so
    satdet is never forced negative.  Non-ok rows stay unevaluated.
    """
    out = dict(result)
    out["gt_has_trail"] = bool(gt["gt_has_trail"])
    out["gt_ntrails"] = len(gt["gt_trails"])
    ok = result.get("state") == "ok"
    if not ok:
        out["is_true_positive"] = None
        out["is_false_positive"] = None
        return out
    detected = bool(result.get("detected", False))
    out["is_true_positive"] = bool(gt["gt_has_trail"] and detected)
    out["is_false_positive"] = bool((not gt["gt_has_trail"]) and detected)
    return out


def summarize(rows):
    """Aggregate assessed rows into descriptive synthetic stats."""
    ok_rows = [r for r in rows if r.get("state") == "ok"]
    positives = [r for r in ok_rows if r.get("gt_has_trail")]
    negatives = [r for r in ok_rows if not r.get("gt_has_trail")]

    n_ok = len(ok_rows)
    n_error = sum(1 for r in rows if r.get("state") == "error")
    n_timeout = sum(1 for r in rows if r.get("state") == "timeout")
    n_unevaluated_positive = sum(
        1 for r in rows if r.get("state") != "ok" and r.get("gt_has_trail"))
    n_unevaluated_negative = sum(
        1 for r in rows if r.get("state") != "ok" and not r.get("gt_has_trail"))

    def _rate(num, den):
        return round(num / den, 3) if den else None

    tp = sum(1 for r in positives if r.get("is_true_positive"))
    fp = sum(1 for r in negatives if r.get("is_false_positive"))
    fn = sum(1 for r in positives if r.get("is_true_positive") is False)
    tn = sum(1 for r in negatives if r.get("is_false_positive") is False)

    fp_by_class = [r["case_id"] for r in negatives if r.get("is_false_positive")]
    fn_by_class = [r["case_id"] for r in positives if r.get("is_true_positive") is False]

    # physical-trail accounting (only positives carry matched/missed/extra)
    phys_matched = sum(r.get("n_matched") or 0 for r in positives)
    phys_total = sum(r.get("gt_ntrails") or 0 for r in positives)
    phys_extra = sum(r.get("n_extra") or 0 for r in positives)
    multi = [r for r in positives if (r.get("gt_ntrails") or 0) > 1]
    multi_coherent = sum(1 for r in multi if r.get("grouping_coherent"))

    runtimes = [r["runtime_s"] for r in ok_rows if r.get("runtime_s") is not None]
    ang_errs = [r["angle_error_deg"] for r in positives
                if isinstance(r.get("angle_error_deg"), (int, float))]

    return {
        "n_cases": len(rows),
        "n_ok": n_ok,
        "n_error": n_error,
        "n_timeout": n_timeout,
        "n_unevaluated_positive": n_unevaluated_positive,
        "n_unevaluated_negative": n_unevaluated_negative,
        "n_positive_cases": len(positives),
        "n_negative_cases": len(negatives),
        "synthetic_tp": tp,
        "synthetic_fp": fp,
        "synthetic_fn": fn,
        "synthetic_tn": tn,
        "synthetic_detection_rate_positives": _rate(tp, len(positives)),
        "synthetic_false_positive_rate_negatives": _rate(fp, len(negatives)),
        "fp_by_class": sorted(fp_by_class),
        "fn_by_class": sorted(fn_by_class),
        # physical-trail localisation / grouping
        "physical_trail_matched": phys_matched,
        "physical_trail_total": phys_total,
        "physical_trail_rate": _rate(phys_matched, phys_total),
        "physical_extras_on_positives": phys_extra,
        "n_multi_trail_cases": len(multi),
        "n_multi_trail_coherent": multi_coherent,
        "mean_angle_error_deg": round(float(np.mean(ang_errs)), 2) if ang_errs else None,
        "runtime_s_mean": round(float(np.mean(runtimes)), 4) if runtimes else None,
        "runtime_s_p50": float(np.percentile(runtimes, 50)) if runtimes else None,
        "runtime_s_p95": float(np.percentile(runtimes, 95)) if runtimes else None,
        "runtime_s_n": len(runtimes),
    }
