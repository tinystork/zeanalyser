#!/usr/bin/env python3
"""CLI runner for the adaptive-Hough trail detector spike (TRAIL-02B).

Runs the **custom** NumPy/SciPy/scikit-image Hough detector on three synthetic
splits (``dev``, ``observed_holdout``, ``blind``) without touching the product.

Usage
-----
    python run_spike.py --quick            # default: size=192
    python run_spike.py --full             # size=256
    python run_spike.py --help
    python run_spike.py --list-cases
    python run_spike.py --check-results [PATH]

Outputs (all under ``--out-dir``, default ``results/``):
    results_run.json    full per-case results (bounded; no pixel dumps)
    results_summary.md  human-readable markdown summary

RSS / runtime measurement
-------------------------
Each ``(split, case)`` custom run is executed in a fresh subprocess so that peak
RSS (``ru_maxrss``, Linux KiB) and wall time are attributable to that run.  A
per-split "import-only" baseline subprocess is subtracted to approximate the
incremental memory of the algorithm (clearly labelled approximation).

Optional coarse comparison (``--compare-001``) runs the public spike-001
``satdet``/``MRT`` adapters **in-process** on ``observed_holdout`` only; those
backend rows carry runtime only (no RSS isolation) and are explicitly *not*
comparable to the isolated custom rows.  Backend detection truth is normalised
via the adapter's own ``detected`` boolean (satdet has ``n_accepted is None``).

Results fingerprints cover both this spike's files and the spike-001
``synthetic.py`` / ``adapters.py`` it depends on (read-only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from synthetic import SPLITS, build_case            # noqa: E402
from detector import CONFIG, detect                 # noqa: E402
from metrics import assess_case, assess_backend_case, summarize  # noqa: E402


# --------------------------------------------------------------------------- #
# Worker protocol (subprocess isolation for runtime / RSS)
# --------------------------------------------------------------------------- #
def _worker_main(args):
    if args.baseline:
        import detector  # noqa: F401  (import-only baseline)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps({"baseline": True, "split": args.split, "rss_kb": rss}))
        return

    split = args.split
    case_id = args.only_cases[0] if args.only_cases else None
    image, gt = build_case(split, case_id, args.size)
    seed = SPLITS[split]["seed"]

    t0 = time.perf_counter()
    result = detect(image, args.size, seed)
    runtime = time.perf_counter() - t0

    result["runtime_s"] = round(runtime, 4)
    result["rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["case_id"] = case_id
    result["split"] = split
    result["size"] = args.size
    result["seed"] = seed
    result["worker_wall_s"] = round(runtime, 4)
    print(json.dumps(result))


def _run_subprocess(args_list, timeout=60):
    """Run a worker subprocess; never raises (maps failures to state)."""
    try:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__)] + args_list,
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "n_accepted": 0, "runtime_s": None,
                "error": f"worker timed out after {timeout}s"}

    try:
        payload = json.loads(proc.stdout.strip())
    except Exception:
        return {"state": "error", "n_accepted": 0, "runtime_s": None,
                "error": "worker did not return valid JSON; stdout="
                + proc.stdout.strip()[:300] + " stderr=" + proc.stderr.strip()[:300]}
    if not isinstance(payload, dict):
        return {"state": "error", "n_accepted": 0, "runtime_s": None,
                "error": "worker JSON payload must be an object"}
    if proc.returncode != 0:
        payload["state"] = "error"
        payload["n_accepted"] = 0
        payload["runtime_s"] = None
        if not payload.get("error"):
            payload["error"] = f"worker exited with code {proc.returncode}"
    return payload


# --------------------------------------------------------------------------- #
# Main custom run (dev + observed_holdout + blind)
# --------------------------------------------------------------------------- #
def run_custom(size, out_dir, only_cases=None, timeout=60):
    split_keys = list(SPLITS.keys())

    baselines = {}
    for sk in split_keys:
        bl = _run_subprocess(["--baseline", "--split", sk], timeout)
        baselines[sk] = bl.get("rss_kb") if bl.get("baseline") else None

    results = {}
    for sk in split_keys:
        case_ids = only_cases or SPLITS[sk]["case_ids"]
        if only_cases:
            case_ids = [c for c in case_ids if c in SPLITS[sk]["case_ids"]]
        rows = []
        for case_id in case_ids:
            image, gt = build_case(sk, case_id, size)
            t_start = time.time()
            payload = _run_subprocess(
                ["--worker", "--split", sk, "--case", case_id,
                 "--size", str(size)], timeout)
            wall = time.time() - t_start
            payload["case_id"] = case_id
            payload["split"] = sk
            payload["worker_wall_s"] = round(wall, 3)
            if payload.get("state") == "ok" and payload.get("rss_kb") is not None \
                    and baselines.get(sk):
                payload["rss_delta_kb"] = max(
                    0, int(payload["rss_kb"]) - int(baselines[sk]))
            else:
                payload["rss_delta_kb"] = None
            rows.append(assess_case(gt, payload))
        results[sk] = rows

    summary = {sk: summarize(results[sk]) for sk in split_keys}
    return results, summary, baselines


# --------------------------------------------------------------------------- #
# Optional coarse comparison vs public 001 backends (in-process)
# --------------------------------------------------------------------------- #
def run_001_comparison(size):
    """Run satdet + MRT (spike-001 adapters, read-only) on ``observed_holdout``.

    Coarse only: in-process, runtime only, no RSS isolation, no timeouts.
    Detection truth is normalised via each adapter's own ``detected`` boolean so
    satdet (``n_accepted is None``) is never forced negative.
    """
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..",
                                                     "001-trail-detector-comparison")))
    from adapters import run_satdet, run_mrt  # noqa: E402
    rows = []
    for case_id in SPLITS["observed_holdout"]["case_ids"]:
        image, gt = build_case("observed_holdout", case_id, size)
        seed = SPLITS["observed_holdout"]["seed"]
        for name, fn in (("satdet", run_satdet), ("mrt", run_mrt)):
            t0 = time.perf_counter()
            if name == "satdet":
                res = fn(image, size, seed)
            else:
                res = fn(image, size, 1.0, seed)
            res["backend_runtime_s"] = round(time.perf_counter() - t0, 4)
            res["runtime_s"] = res["backend_runtime_s"]
            res["case_id"] = case_id
            res["split"] = "observed_holdout"
            res["_comparison"] = True
            rows.append(assess_backend_case(gt, res))
    return {"satdet": summarize([r for r in rows if r.get("backend") == "acstools.satdet"]),
            "mrt": summarize([r for r in rows if r.get("backend") == "acstools.findsat_mrt"]),
            "rows": rows}


# --------------------------------------------------------------------------- #
# Fingerprints + mechanical validation
# --------------------------------------------------------------------------- #
# Explicit relative keys (from this spike dir); includes the read-only spike-001
# files that the results depend on.
_RESULT_FILES = [
    "synthetic.py", "detector.py", "metrics.py", "run_spike.py",
    "../001-trail-detector-comparison/synthetic.py",
    "../001-trail-detector-comparison/adapters.py",
]


def _fingerprints():
    fps = {}
    for fn in _RESULT_FILES:
        p = os.path.normpath(os.path.join(HERE, fn))
        with open(p, "rb") as f:
            fps[fn] = hashlib.sha256(f.read()).hexdigest()
    return fps


def check_results(path):
    try:
        return _check_results_impl(path)
    except Exception as exc:
        return 1, f"results payload failed validation: {type(exc).__name__}: {exc}"


_FLOAT_KEYS = {"runtime_s_mean", "runtime_s_p50", "runtime_s_p95",
               "mean_angle_error_deg", "physical_trail_rate"}


def _summaries_match(orig, recomputed, where):
    """Compare two ``summarize()`` dicts; return ``(ok, message)``."""
    if not isinstance(orig, dict):
        return False, f"{where}: summary must be an object"
    if set(orig.keys()) != set(recomputed.keys()):
        return False, f"{where}: summary keys differ: " \
                      f"{sorted(set(orig) ^ set(recomputed))!r}"
    for k, v in recomputed.items():
        o = orig[k]
        if k in _FLOAT_KEYS:
            if v is None or o is None:
                if v != o:
                    return False, f"{where}.{k}: {o!r} != {v!r}"
            elif abs(v - o) > 1e-6 * max(1.0, abs(v), abs(o)):
                return False, f"{where}.{k}: {o!r} != {v!r}"
        elif o != v:
            return False, f"{where}.{k}: {o!r} != {v!r}"
    return True, ""


def _check_comparison(comp):
    """Validate the saved spike-001 comparison block (fix 3).

    Requires ``rows`` = each observed_holdout case x 2 backends exactly once,
    then recomputes the ``satdet``/``mrt`` summaries and compares them.
    """
    if not isinstance(comp, dict):
        return False, "comparison must be an object"
    rows = comp.get("rows")
    if not isinstance(rows, list):
        return False, "comparison.rows must be a list"
    backend_labels = ["acstools.satdet", "acstools.findsat_mrt"]
    obs_cases = SPLITS["observed_holdout"]["case_ids"]
    expected = {(c, b) for c in obs_cases for b in backend_labels}
    seen = {}
    for r in rows:
        if not isinstance(r, dict):
            return False, "each comparison row must be an object"
        key = (r.get("case_id"), r.get("backend"))
        if key not in expected:
            return False, f"unexpected comparison pair {key!r}"
        if key in seen:
            return False, f"duplicate comparison pair {key!r}"
        seen[key] = r
    missing = expected - set(seen)
    if missing:
        return False, f"missing comparison pairs: {sorted(missing)!r}"
    for b in ("satdet", "mrt"):
        label = "acstools.satdet" if b == "satdet" else "acstools.findsat_mrt"
        subset = [r for r in rows if r.get("backend") == label]
        ok, msg = _summaries_match(comp.get(b), summarize(subset), f"comparison[{b}]")
        if not ok:
            return False, msg
    return True, ""


def _check_results_impl(path):
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return 1, f"results file not found: {path}"
    except Exception as exc:
        return 1, f"results unreadable/invalid JSON: {type(exc).__name__}: {exc}"

    if not isinstance(payload, dict):
        return 1, "results payload must be an object"
    meta = payload.get("meta")
    results = payload.get("results")
    summary = payload.get("summary")
    if not isinstance(meta, dict) or not isinstance(results, dict) \
            or not isinstance(summary, dict):
        return 1, "payload must contain meta (object), results (object), summary (object)"

    for sk in SPLITS:
        case_ids = meta.get(f"{sk}_case_ids")
        rows = results.get(sk)
        if not isinstance(case_ids, list) or not case_ids:
            return 1, f"meta.{sk}_case_ids must be a non-empty list"
        if not isinstance(rows, list):
            return 1, f"results.{sk} must be a list"
        seen = {}
        for r in rows:
            if not isinstance(r, dict):
                return 1, f"results.{sk} row must be an object"
            key = r.get("case_id")
            if key not in case_ids:
                return 1, f"unexpected case {key!r} in split {sk}"
            if key in seen:
                return 1, f"duplicate case {key!r} in split {sk}"
            seen[key] = r
        missing = [c for c in case_ids if c not in seen]
        if missing:
            return 1, f"missing cases in {sk}: {missing!r}"

        recomputed = summarize(rows)
        ok, msg = _summaries_match(summary.get(sk), recomputed, f"summary[{sk}]")
        if not ok:
            return 1, msg

    fps = meta.get("fingerprints")
    if not isinstance(fps, dict):
        return 1, "meta.fingerprints must be an object"
    current = _fingerprints()
    for fn, h in current.items():
        if fps.get(fn) != h:
            return 1, f"fingerprint mismatch for {fn}: saved={fps.get(fn)} current={h}"
    for fn in fps:
        if fn not in current:
            return 1, f"unexpected fingerprint key {fn!r}"

    comp = payload.get("comparison")
    comp_note = ""
    if comp is not None:
        ok, msg = _check_comparison(comp)
        if not ok:
            return 1, msg
        comp_note = ", comparison OK"
    else:
        comp_note = ", comparison absent (accepted)"

    parts = ", ".join(f"{sk}={len(results[sk])} rows" for sk in SPLITS)
    return 0, f"results valid: {parts}, summary + fingerprints OK{comp_note}"


# --------------------------------------------------------------------------- #
# Markdown summary
# --------------------------------------------------------------------------- #
def _write_markdown(payload, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    meta = payload["meta"]
    L = []
    L.append("# Spike TRAIL-02B — Hough adaptatif (corpus synthétique)")
    L.append("")
    L.append(f"- size={meta['size']} px, seeds: "
             + ", ".join(f"{sk}={meta['seed_' + sk]}" for sk in SPLITS))
    L.append(f"- RSS method: {meta['rss_method']}")
    L.append(f"- baselines (import-only, KiB): "
             + ", ".join(f"{k}={v}" for k, v in meta["rss_baselines_kb"].items()))
    L.append("")
    for sk in SPLITS:
        L.append(f"## Split `{sk}` — tableau par cas")
        L.append("")
        L.append("| case | state | t(s) | trails | acc | verdict | matched/GT | "
                 "angle_err | offset_px | endpt_px | score |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in payload["results"][sk]:
            if r.get("state") != "ok":
                verdict = r.get("state", "?")
            elif r.get("is_false_positive"):
                verdict = "FP"
            elif r.get("is_true_positive"):
                verdict = "TP"
            elif r.get("gt_has_trail"):
                verdict = "FN"
            else:
                verdict = "TN"
            t = r.get("runtime_s")
            t = f"{t:.3f}" if isinstance(t, (int, float)) else "-"
            ang = r.get("angle_error_deg")
            ang = f"{ang:.1f}" if isinstance(ang, (int, float)) else "-"
            off = r.get("offset_error_px")
            off = f"{off:.1f}" if isinstance(off, (int, float)) else "-"
            ep = r.get("endpoint_error_px")
            ep = f"{ep:.1f}" if isinstance(ep, (int, float)) else "-"
            mg = f"{r.get('n_matched')}/{r.get('gt_ntrails')}" if r.get("gt_has_trail") else "-"
            score = ""
            if r.get("trails"):
                tops = sorted([t for t in r["trails"] if t.get("accepted")],
                              key=lambda x: -x["score"])
                if tops:
                    score = f"{tops[0]['score']:.2f}"
            L.append(f"| {r['case_id']} | {r['state']} | {t} | {r.get('n_trails')} "
                     f"| {r.get('n_accepted')} | {verdict} | {mg} | {ang} | {off} "
                     f"| {ep} | {score} |")
        L.append("")
        s = payload["summary"][sk]
        L.append(f"### Synthèse `{sk}` (labels *synthetic*, pas produit)")
        L.append(f"- ok={s['n_ok']} erreur={s['n_error']} timeout={s['n_timeout']}")
        L.append(f"- positives={s['n_positive_cases']} négatifs={s['n_negative_cases']}")
        L.append(f"- TP={s['synthetic_tp']} FP={s['synthetic_fp']} "
                 f"FN={s['synthetic_fn']} TN={s['synthetic_tn']}")
        L.append(f"- détection (positives)={s['synthetic_detection_rate_positives']} "
                 f"FP rate (négatifs)={s['synthetic_false_positive_rate_negatives']}")
        L.append(f"- FP par classe={s['fp_by_class']}  FN par classe={s['fn_by_class']}")
        L.append(f"- traces physiques: matched={s['physical_trail_matched']}/"
                 f"{s['physical_trail_total']} (taux={s['physical_trail_rate']}), "
                 f"extras sur positifs={s['physical_extras_on_positives']}, "
                 f"multi-traces cohérentes={s['n_multi_trail_coherent']}/"
                 f"{s['n_multi_trail_cases']}")
        if s.get("mean_angle_error_deg") is not None:
            L.append(f"- erreur angle moyenne={s['mean_angle_error_deg']}°")
        L.append(f"- temps: mean={s['runtime_s_mean']}s p50={s['runtime_s_p50']}s "
                 f"p95={s['runtime_s_p95']}s (n={s['runtime_s_n']})")
        L.append("")
    if payload.get("comparison"):
        L.append("## Comparaison grossière (satdet/MRT publics 001, observed_holdout)")
        L.append("")
        L.append("*In-process, runtime seul, non isolé RSS — non comparable aux "
                 "lignes custom isolées.*")
        L.append("")
        for b, s in payload["comparison"].items():
            if b == "rows":
                continue
            L.append(f"- **{b}**: détection={s['synthetic_detection_rate_positives']} "
                     f"FP rate={s['synthetic_false_positive_rate_negatives']} "
                     f"FP={s['fp_by_class']} FN={s['fn_by_class']}")
        L.append("")
    md_path = os.path.join(out_dir, "results_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return md_path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Spike TRAIL-02B: adaptive Hough trail detector (custom).")
    ap.add_argument("--quick", action="store_true", default=True)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    ap.add_argument("--case", dest="only_cases", action="append",
                    help="restrict to case id (repeatable)")
    ap.add_argument("--list-cases", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--compare-001", action="store_true",
                    help="run satdet/MRT public 001 backends on observed_holdout (coarse)")
    ap.add_argument("--check-results", nargs="?",
                    const=os.path.join(HERE, "results", "results_run.json"),
                    default=None)

    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--baseline", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--split", choices=list(SPLITS), help=argparse.SUPPRESS)

    args = ap.parse_args(argv)

    if args.worker or args.baseline:
        _worker_main(args)
        return 0

    if args.list_cases:
        for sk in SPLITS:
            print(f"[{sk}]")
            print("  " + " ".join(SPLITS[sk]["case_ids"]))
        return 0

    if args.check_results:
        code, msg = check_results(args.check_results)
        print(msg)
        return code

    size = 256 if args.full else 192
    if args.size is not None:
        size = args.size

    results, summary, baselines = run_custom(size, args.out_dir,
                                             only_cases=args.only_cases,
                                             timeout=args.timeout)
    meta = {
        "mission": "ZA-TRAIL-02B-ADAPTIVE-HOUGH-SPIKE-20261002",
        "size": size,
        "rss_method": ("resource.getrusage(RUSAGE_SELF).ru_maxrss (child peak, KiB); "
                       "delta = child peak - import-only baseline"),
        "rss_baselines_kb": baselines,
        "config": CONFIG,
        "fingerprints": _fingerprints(),
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for sk in SPLITS:
        meta[f"seed_{sk}"] = SPLITS[sk]["seed"]
        meta[f"{sk}_case_ids"] = SPLITS[sk]["case_ids"]
    payload = {"meta": meta, "results": results, "summary": summary}

    if args.compare_001:
        payload["comparison"] = run_001_comparison(size)

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "results_run.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    md_path = _write_markdown(payload, args.out_dir)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps({sk: summary[sk] for sk in SPLITS}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
