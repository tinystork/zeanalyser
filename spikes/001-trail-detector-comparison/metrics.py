"""Assessment and aggregation helpers for the satdet-vs-MRT spike.

All metrics here are explicitly **synthetic**: they describe behaviour on the
deterministic synthetic corpus only.  They are *not* product recall / precision,
and no product threshold is derived from them.

A technical failure (``state != "ok"``, i.e. ``error`` or ``timeout``) is **not**
a false negative/true negative: only rows with ``state == "ok"`` feed the
synthetic TP/FP/FN/TN counts and rates.  Non-ok rows are reported separately as
``n_error`` / ``n_timeout`` / ``n_unevaluated_positive`` / ``n_unevaluated_negative``.
"""

from __future__ import annotations

import numpy as np


def angular_distance_deg(a, b):
    """Minimum angular distance in [0, 180) orientation space."""
    d = abs((a % 180.0) - (b % 180.0)) % 180.0
    return min(d, 180.0 - d)


def assess_case(gt, result):
    """Attach synthetic per-case metrics to a backend result.

    Returns a shallow copy of ``result`` enriched with:
      * ``gt_has_trail``
      * ``is_true_positive`` / ``is_false_positive`` (synthetic, image level).
        These are ``None`` (not ``False``) when ``state != "ok"`` so that a
        technical failure is never silently counted as FN/TN.
      * ``angle_error_deg``: coarse localisation for single-trail positives
        (nearest detected angle to ground truth), or ``None`` when not
        applicable (non-ok, multi-trail, no candidates, or no ground truth).
    """
    out = dict(result)
    out["gt_has_trail"] = gt["gt_has_trail"]
    out["gt_ntrails"] = len(gt["gt_trails"])

    ok = result.get("state") == "ok"
    detected = bool(result.get("detected", False))

    out["angle_error_deg"] = None
    if not ok:
        # Technical failure: no binary verdict, no localisation.
        out["is_true_positive"] = None
        out["is_false_positive"] = None
        return out

    out["is_true_positive"] = bool(gt["gt_has_trail"] and detected)
    out["is_false_positive"] = bool((not gt["gt_has_trail"]) and detected)

    # Coarse localisation: only meaningful for single-trail positives with a
    # detected candidate.  Position (offset/rho) is NOT comparable between the
    # two backends and is deliberately left out.
    if gt["gt_has_trail"] and len(gt["gt_trails"]) == 1 and detected:
        angs = result.get("angles_deg") or []
        if angs:
            target = gt["gt_trails"][0]["angle_deg"]
            out["angle_error_deg"] = min(
                angular_distance_deg(a, target) for a in angs)
    return out


def summarize(results):
    """Aggregate a list of assessed per-case results into descriptive stats.

    ``results`` must already be assessed (``assess_case`` applied).
    Only ``state == "ok"`` rows are evaluated; technical failures are counted
    separately (``n_error``, ``n_timeout``) and, among them, how many were
    positives vs negatives (``n_unevaluated_positive``/``n_unevaluated_negative``).
    """
    ok_rows = [r for r in results if r.get("state") == "ok"]
    positives = [r for r in ok_rows if r.get("gt_has_trail")]
    negatives = [r for r in ok_rows if not r.get("gt_has_trail")]

    n_ok = len(ok_rows)
    n_error = sum(1 for r in results if r.get("state") == "error")
    n_timeout = sum(1 for r in results if r.get("state") == "timeout")
    n_unevaluated_positive = sum(
        1 for r in results if r.get("state") != "ok" and r.get("gt_has_trail"))
    n_unevaluated_negative = sum(
        1 for r in results if r.get("state") != "ok" and not r.get("gt_has_trail"))

    def _rate(num, den):
        return round(num / den, 3) if den else None

    tp = sum(1 for r in positives if r.get("is_true_positive"))
    fp = sum(1 for r in negatives if r.get("is_false_positive"))
    fn = sum(1 for r in positives if r.get("is_true_positive") is False)
    tn = sum(1 for r in negatives if r.get("is_false_positive") is False)

    runtimes = [r["runtime_s"] for r in ok_rows
                if r.get("runtime_s") is not None]
    p50 = float(np.percentile(runtimes, 50)) if runtimes else None
    p95 = float(np.percentile(runtimes, 95)) if runtimes else None

    return {
        "n_cases": len(results),
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
        "runtime_s_mean": round(float(np.mean(runtimes)), 4) if runtimes else None,
        "runtime_s_p50": p50,
        "runtime_s_p95": p95,
        "runtime_s_n": len(runtimes),
    }
