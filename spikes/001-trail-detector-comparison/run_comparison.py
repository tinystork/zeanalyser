#!/usr/bin/env python3
"""CLI runner for the satdet-vs-MRT trail detector spike (TRAIL-02A).

This is a **spike** harness: it compares ``acstools.satdet`` and
``acstools.findsat_mrt.TrailFinder`` on the same deterministic synthetic corpus
(``synthetic.py``) without touching the product.

Usage
-----
    python run_comparison.py --quick            # default: 192 px, theta 1.0 deg
    python run_comparison.py --full             # 256 px, theta 0.5 deg
    python run_comparison.py --help
    python run_comparison.py --list-cases

Outputs (all under ``--out-dir``, default ``results/``):
    results_run.json    full per-case results (schema in ``adapters.py``)
    results_summary.md  human-readable markdown summary
    (a summary JSON is printed to stdout as well)

RSS / runtime measurement
-------------------------
Each ``(case, backend)`` run is executed in a fresh subprocess so that the peak
RSS (``resource.getrusage(RUSAGE_SELF).ru_maxrss``, Linux: KiB) and wall-clock
time are attributable to that single run.  A per-backend "baseline" subprocess
(imports the adapter, does nothing) is subtracted to approximate the
incremental memory of the algorithm (this is an approximation: interpreter +
library import cost is excluded from the delta but the metric is clearly
labelled as such).
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

from synthetic import CASE_IDS, build_case          # noqa: E402
from adapters import BACKENDS                       # noqa: E402
from metrics import assess_case, summarize          # noqa: E402

DEFAULT_SEED = 20261002


# --------------------------------------------------------------------------- #
# Subprocess worker protocol
# --------------------------------------------------------------------------- #
def _worker_main(args):
    """Run one case through one backend and print JSON to stdout."""
    if args.baseline:
        backend = args.backend
        # Import-only baseline: just exercise the adapter module surface.
        import adapters  # noqa: F401
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps({"baseline": True, "backend": backend,
                          "rss_kb": rss}))
        return

    case_id = args.only_cases[0] if args.only_cases else None
    image, gt = build_case(case_id, args.size, args.seed)
    runner = BACKENDS[args.backend]["run"]
    if args.backend == "satdet":
        result = runner(image, args.size, args.seed)
    else:  # mrt
        result = runner(image, args.size, args.theta_step, args.seed)
    result["rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["case_id"] = case_id
    result["size"] = args.size
    result["theta_step"] = args.theta_step
    result["seed"] = args.seed
    print(json.dumps(result))


def _run_subprocess(args_list, timeout=120):
    """Run a worker subprocess, returning a common payload or an error/timeout
    dict.  Never raises: TimeoutExpired, nonzero exits, and non-object JSON are
    mapped to ``state`` so the whole run cannot crash on a single worker.
    """
    try:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__)] + args_list,
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "detected": False, "runtime_s": None,
                "error": f"worker timed out after {timeout}s"}

    # JSON absent/invalid => technical error (bounded, useful message).
    try:
        payload = json.loads(proc.stdout.strip())
    except Exception:
        return {"state": "error", "detected": False, "runtime_s": None,
                "error": "worker did not return valid JSON; stdout="
                + proc.stdout.strip()[:300] + " stderr="
                + proc.stderr.strip()[:300]}

    # Valid JSON but not an object (list/null/string/number) => technical error.
    if not isinstance(payload, dict):
        return {"state": "error", "detected": False, "runtime_s": None,
                "error": "worker JSON payload must be an object (got "
                + type(payload).__name__ + ")"}

    # Nonzero exit is a technical failure regardless of what the worker printed.
    if proc.returncode != 0:
        payload["state"] = "error"
        payload["detected"] = False
        payload["runtime_s"] = None
        if not payload.get("error"):
            payload["error"] = f"worker exited with code {proc.returncode}"
    return payload


# --------------------------------------------------------------------------- #
# Main run
# --------------------------------------------------------------------------- #
def run_all(size, theta_step, seed, out_dir, only_cases=None, timeout=120):
    case_ids = only_cases or CASE_IDS

    # Reject unknown case ids before doing any work (fail fast, clear error).
    unknown = [c for c in case_ids if c not in CASE_IDS]
    if unknown:
        raise ValueError(
            f"Unknown case id(s) {unknown!r}; known ids: {CASE_IDS}")

    # Baseline RSS per backend (import-only).
    baselines = {}
    for bkey in BACKENDS:
        bl = _run_subprocess(["--baseline", "--backend", bkey], timeout)
        baselines[bkey] = bl.get("rss_kb") if bl.get("baseline") else None

    rows = []
    for case_id in case_ids:
        image, gt = build_case(case_id, size, seed)
        for bkey, bmeta in BACKENDS.items():
            t_start = time.time()
            payload = _run_subprocess(
                ["--worker", "--case", case_id, "--backend", bkey,
                 "--size", str(size), "--theta-step", str(theta_step),
                 "--seed", str(seed)], timeout)
            wall = time.time() - t_start
            payload["case_id"] = case_id
            payload["backend"] = bmeta["label"]
            payload["worker_wall_s"] = round(wall, 3)
            if payload.get("state") == "ok" and payload.get("rss_kb") is not None \
                    and baselines.get(bkey):
                payload["rss_delta_kb"] = max(
                    0, int(payload["rss_kb"]) - int(baselines[bkey]))
            else:
                payload["rss_delta_kb"] = None
            rows.append(assess_case(gt, payload))

    by_backend = {}
    for bkey, bmeta in BACKENDS.items():
        subset = [r for r in rows if r.get("backend") == bmeta["label"]]
        by_backend[bmeta["label"]] = summarize(subset)

    return {
        "meta": {
            "mission": "ZA-TRAIL-02A-SATDET-MRT-SPIKE-20261002",
            "size": size,
            "theta_step": theta_step,
            "seed": seed,
            "rss_method": ("resource.getrusage(RUSAGE_SELF).ru_maxrss (child "
                           "peak, KiB); delta = child peak - import-only "
                           "baseline"),
            "rss_baselines_kb": baselines,
            "case_ids": case_ids,
            "fingerprints": _fingerprints(),
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "results": rows,
        "summary": by_backend,
    }


# --------------------------------------------------------------------------- #
# Result reproducibility fingerprint + mechanical validation
# --------------------------------------------------------------------------- #
_RESULT_FILES = ["synthetic.py", "adapters.py", "metrics.py",
                 "run_comparison.py"]


def _fingerprints():
    """SHA-256 of the files that determine results, at run/check time."""
    fps = {}
    for fn in _RESULT_FILES:
        p = os.path.join(HERE, fn)
        with open(p, "rb") as f:
            fps[fn] = hashlib.sha256(f.read()).hexdigest()
    return fps


def check_results(path):
    """Validate saved results without ever propagating malformed-input errors."""
    try:
        return _check_results_impl(path)
    except Exception as exc:
        return 1, ("results payload failed validation: "
                   f"{type(exc).__name__}: {exc}")


def _check_results_impl(path):
    """Mechanically validate a saved results JSON.

    Returns ``(code, message)`` with ``code == 0`` on success (exit 0 for the
    CLI), nonzero otherwise.  Checks: payload is an object with
    meta/results/summary; ``meta.case_ids`` and both backends are covered by
    exactly one row each (no duplicate/missing/unexpected pair); the summary is
    recomputed from ``rows`` and compared (exact for counts/rates, tolerance for
    runtime floats); and the file fingerprints match the current source files.
    """
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return 1, f"results file not found: {path}"
    except Exception as exc:
        return 1, f"results file unreadable/invalid JSON: {type(exc).__name__}: {exc}"

    if not isinstance(payload, dict):
        return 1, "results payload must be an object"
    meta = payload.get("meta")
    results = payload.get("results")
    summary = payload.get("summary")
    if not isinstance(meta, dict) or not isinstance(results, list) \
            or not isinstance(summary, dict):
        return 1, "payload must contain meta (object), results (list), summary (object)"

    case_ids = meta.get("case_ids")
    if not isinstance(case_ids, list) or not case_ids:
        return 1, "meta.case_ids must be a non-empty list"
    backend_labels = [b["label"] for b in BACKENDS.values()]

    expected = set()
    for c in case_ids:
        for b in backend_labels:
            expected.add((c, b))

    seen = {}
    for r in results:
        if not isinstance(r, dict):
            return 1, "each result row must be an object"
        key = (r.get("case_id"), r.get("backend"))
        if key not in expected:
            return 1, f"unexpected result pair {key!r}"
        if key in seen:
            return 1, f"duplicate result pair {key!r}"
        seen[key] = r
    missing = expected - set(seen)
    if missing:
        return 1, f"missing result pairs: {sorted(missing)!r}"

    # Recompute summary from rows and compare.
    recomputed = {}
    for b in backend_labels:
        subset = [r for r in results if r.get("backend") == b]
        recomputed[b] = summarize(subset)
    float_keys = {"runtime_s_mean", "runtime_s_p50", "runtime_s_p95"}
    for b in backend_labels:
        orig = summary.get(b)
        s = recomputed[b]
        if not isinstance(orig, dict):
            return 1, f"summary missing/invalid for backend {b}"
        if set(orig.keys()) != set(s.keys()):
            return 1, (f"summary keys differ for {b}: "
                       f"{sorted(set(orig) ^ set(s))!r}")
        for k, v in s.items():
            o = orig[k]
            if k in float_keys:
                if v is None or o is None:
                    if v != o:
                        return 1, f"summary mismatch {b}.{k}: {o!r} != {v!r}"
                elif abs(v - o) > 1e-6 * max(1.0, abs(v), abs(o)):
                    return 1, f"summary mismatch {b}.{k}: {o!r} != {v!r}"
            elif o != v:
                return 1, f"summary mismatch {b}.{k}: {o!r} != {v!r}"

    # Fingerprint check.
    fps = meta.get("fingerprints")
    if not isinstance(fps, dict):
        return 1, "meta.fingerprints must be an object"
    current = _fingerprints()
    for fn, h in current.items():
        if fps.get(fn) != h:
            return 1, (f"fingerprint mismatch for {fn}: "
                       f"saved={fps.get(fn)} current={h}")
    for fn in fps:
        if fn not in current:
            return 1, f"unexpected fingerprint key {fn!r}"

    return 0, (f"results valid: {len(results)} rows, "
               f"{len(case_ids)} cases x {len(backend_labels)} backends, "
               f"summary and fingerprints OK")


def _write_markdown(payload, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    meta = payload["meta"]
    lines = []
    lines.append("# Spike TRAIL-02A — satdet vs MRT (corpus synthétique)")
    lines.append("")
    lines.append(f"- size={meta['size']} px, theta_step={meta['theta_step']}°, "
                 f"seed={meta['seed']}")
    lines.append(f"- RSS method: {meta['rss_method']}")
    lines.append(f"- baselines (import-only, KiB): "
                 + ", ".join(f"{k}={v}" for k, v in meta["rss_baselines_kb"].items()))
    lines.append("")
    lines.append("## Tableau par cas")
    lines.append("")
    lines.append("| case | backend | state | t(s) | detected | seg/sources | "
                 "acc(2)/cand(1) | FP | angle_err |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in payload["results"]:
        det = "O" if r.get("detected") else "."
        if r.get("state") != "ok":
            fp = r.get("state", "?")
        elif r.get("is_false_positive"):
            fp = "FP"
        elif r.get("is_true_positive"):
            fp = "TP"
        elif r.get("gt_has_trail"):
            fp = "FN"
        else:
            fp = "TN"
        nseg = r.get("n_segments")
        nsrc = r.get("n_sources")
        seg_src = f"{nseg}" if nseg is not None else f"{nsrc}"
        acc = r.get("n_accepted")
        cand = r.get("n_candidate")
        acc_cand = f"{acc}/{cand}" if acc is not None else "-"
        ang = r.get("angle_error_deg")
        ang = f"{ang:.1f}" if isinstance(ang, (int, float)) else "-"
        t = r.get("runtime_s")
        t = f"{t:.3f}" if isinstance(t, (int, float)) else "-"
        lines.append(f"| {r['case_id']} | {r['backend']} | {r['state']} | {t} | "
                     f"{det} | {seg_src} | {acc_cand} | {fp} | {ang} |")
    lines.append("")
    lines.append("## Synthèse synthétique (labels *synthetic*, pas produit)")
    lines.append("")
    for label, s in payload["summary"].items():
        lines.append(f"### {label}")
        lines.append(f"- évalués ok={s['n_ok']} erreur={s['n_error']} timeout={s['n_timeout']} "
                     f"(non évalués: positif={s['n_unevaluated_positive']} "
                     f"négatif={s['n_unevaluated_negative']})")
        lines.append(f"- positives={s['n_positive_cases']} négatifs={s['n_negative_cases']}")
        lines.append(f"- TP={s['synthetic_tp']} FP={s['synthetic_fp']} "
                     f"FN={s['synthetic_fn']} TN={s['synthetic_tn']}")
        lines.append(f"- détection (positives)={s['synthetic_detection_rate_positives']} "
                     f"FP rate (négatifs)={s['synthetic_false_positive_rate_negatives']}")
        lines.append(f"- temps: mean={s['runtime_s_mean']}s "
                     f"p50={s['runtime_s_p50']}s p95={s['runtime_s_p95']}s "
                     f"(n={s['runtime_s_n']})")
        lines.append("")
    md_path = os.path.join(out_dir, "results_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return md_path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Spike TRAIL-02A: compare acstools.satdet vs findsat_mrt.")
    ap.add_argument("--quick", action="store_true", default=True,
                    help="quick mode (default): size=192, theta_step=1.0")
    ap.add_argument("--full", action="store_true",
                    help="full mode: size=256, theta_step=0.5")
    ap.add_argument("--size", type=int, default=None,
                    help="override image size (px)")
    ap.add_argument("--theta-step", type=float, default=None,
                    help="override MRT theta step (deg)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    ap.add_argument("--case", dest="only_cases", action="append",
                    choices=CASE_IDS,
                    help="restrict to one case id (repeatable)")
    ap.add_argument("--list-cases", action="store_true")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="per-case subprocess timeout (s)")
    ap.add_argument("--check-results", nargs="?",
                    const=os.path.join(HERE, "results", "results_run.json"),
                    default=None,
                    help="validate a saved results JSON and exit "
                         "(default: results/results_run.json)")

    # Hidden worker protocol flags (not part of the public CLI surface).
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--baseline", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--backend", choices=list(BACKENDS), help=argparse.SUPPRESS)

    args = ap.parse_args(argv)

    if args.worker or args.baseline:
        _worker_main(args)
        return 0

    if args.list_cases:
        print("\n".join(CASE_IDS))
        return 0

    if args.check_results:
        code, msg = check_results(args.check_results)
        print(msg)
        return code

    if args.full:
        size = 256
        theta_step = 0.5
    else:
        size = 192
        theta_step = 1.0
    if args.size is not None:
        size = args.size
    if args.theta_step is not None:
        theta_step = args.theta_step

    payload = run_all(size, theta_step, args.seed, args.out_dir,
                      only_cases=args.only_cases, timeout=args.timeout)
    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "results_run.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    md_path = _write_markdown(payload, args.out_dir)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
