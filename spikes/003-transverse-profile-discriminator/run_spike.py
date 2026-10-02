"""CLI runner for the transverse-profile discriminator spike (TRAIL-02C).

Runs the profile-level discriminator on the ``dev`` and ``blind`` splits
(synthetic 1-D transverse profiles), plus an optional end-to-end probe that
re-uses spike-002 read-only.

Usage
-----
    python run_spike.py --dev            # profile-level dev split (threshold choice)
    python run_spike.py --blind          # profile-level blind split (frozen)
    python run_spike.py --probe          # end-to-end probe vs spike-002 (quick=192)
    python run_spike.py --probe --full   # end-to-end probe at 256 px
    python run_spike.py --check-results [PATH]

Outputs (under ``--out-dir``, default ``results/``):
    results_run.json    full per-case results (bounded; no pixel dumps)
    results_summary.md  human-readable markdown summary
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import profile_models as pm             # noqa: E402
from profile_models import CONFIG, discriminate_profile, default_offsets  # noqa: E402
import synthetic_profiles as sp          # noqa: E402
from synthetic_profiles import (BLIND_SEED, DEV_SEED, SPLITS,  # noqa: E402
                                build_case, sample_profile_from_image)


# --------------------------------------------------------------------------- #
# Profile-level evaluation
# --------------------------------------------------------------------------- #
def assess_profile(case_id, gt, decision):
    """Attach the profile-level confusion to a decision dict."""
    out = dict(decision)
    out["case_id"] = case_id
    out["gt_label"] = gt["label"]
    out["kind"] = gt.get("kind")
    out["predicted"] = decision["label"]

    # descriptive parameter error (sigma for ridge, width for column)
    err = None
    if gt.get("kind") == "ridge" and decision.get("ridge"):
        err = abs(decision["ridge"]["params"]["sigma"] - gt["sigma"])
        out["sigma_err"] = round(err, 4)
    elif gt.get("kind") == "column" and decision.get("column"):
        err = abs(decision["column"]["params"]["width"] - gt["width"])
        out["width_err"] = round(err, 4)

    if gt["label"] == decision["label"]:
        out["correct"] = True
    elif decision["label"] == "ambiguous":
        out["correct"] = False
        out["outcome"] = "missed_ambiguous"
    else:
        out["correct"] = False
        out["outcome"] = "confusion"
    return out


def _confusion_summary(rows):
    """3x3 ridge/column/ambiguous confusion over profile-level rows."""
    import numpy as np
    labels = ["ridge", "column", "ambiguous"]
    mat = {g: {p: 0 for p in labels} for g in labels}
    n_amb_gt = n_amb_pred = 0
    n_conv = 0
    runtimes = []
    delta = []
    for r in rows:
        g, p = r["gt_label"], r["predicted"]
        mat[g][p] += 1
        if g == "ambiguous":
            n_amb_gt += 1
        if p == "ambiguous":
            n_amb_pred += 1
        if r.get("converged"):
            n_conv += 1
        if isinstance(r.get("runtime_s"), (int, float)):
            runtimes.append(r["runtime_s"])
        if r.get("preference") is not None:
            delta.append(r["preference"])

    # derived profile-level metrics
    ridge_gt = sum(mat["ridge"].values())
    col_gt = sum(mat["column"].values())
    amb_gt = sum(mat["ambiguous"].values())
    ridge_ok = mat["ridge"]["ridge"]
    col_ok = mat["column"]["column"]
    amb_ok = mat["ambiguous"]["ambiguous"]

    return {
        "n_cases": len(rows),
        "confusion": mat,
        "n_converged": n_conv,
        "n_ambiguous_gt": n_amb_gt,
        "n_ambiguous_pred": n_amb_pred,
        # ridge recall = true ridges labelled ridge; ridge "rejected" = labelled column
        "ridge_recall": round(ridge_ok / ridge_gt, 3) if ridge_gt else None,
        "ridge_misclass_column": mat["ridge"]["column"],
        "ridge_ambiguous": mat["ridge"]["ambiguous"],
        # column precision = true columns labelled column; column "accepted" = labelled ridge
        "column_recall": round(col_ok / col_gt, 3) if col_gt else None,
        "column_misclass_ridge": mat["column"]["ridge"],
        "column_ambiguous": mat["column"]["ambiguous"],
        # ambiguous handling
        "ambiguous_ok": amb_ok,
        "ambiguous_promoted": amb_gt - amb_ok,
        "runtime_s_mean": round(float(np.mean(runtimes)), 4) if runtimes else None,
        "runtime_s_p50": float(np.percentile(runtimes, 50)) if runtimes else None,
        "runtime_s_p95": float(np.percentile(runtimes, 95)) if runtimes else None,
    }


def run_profile(split, out_dir):
    offsets = default_offsets()
    rows = []
    for case_id in SPLITS[split]["cases"]:
        image, p0, p1, gt = build_case(split, case_id)
        profile, noise, coverage = sample_profile_from_image(image, p0, p1, offsets)
        t0 = time.perf_counter()
        # Use the image/residual MAD noise (global, robust to the sparse
        # structure) — consistent with the probe; the profile-level MAD inside
        # discriminate_profile is only the API fallback when noise is None.
        decision = discriminate_profile(profile, offsets, noise=noise)
        runtime = time.perf_counter() - t0
        decision["runtime_s"] = round(runtime, 6)
        decision["coverage"] = round(coverage, 4)
        decision["noise"] = round(noise, 4)
        rows.append(assess_profile(case_id, gt, decision))
    return rows, _confusion_summary(rows)


# --------------------------------------------------------------------------- #
# End-to-end probe: re-use spike-002 read-only, replace the shape gates
# --------------------------------------------------------------------------- #
def run_probe(size, out_dir=None):
    """Run spike-002 pipeline + model-003 shape decision on the 002 blind split
    and a fixed 003 audit, reporting the baseline-vs-probe difference."""
    import run_probe_impl
    return run_probe_impl.run(size)


# --------------------------------------------------------------------------- #
# Fingerprints
# --------------------------------------------------------------------------- #
_RESULT_FILES = [
    "profile_models.py", "synthetic_profiles.py", "run_spike.py",
    "run_probe_impl.py",
    "../002-adaptive-hough-trail-detector/detector.py",
    "../002-adaptive-hough-trail-detector/synthetic.py",
    "../002-adaptive-hough-trail-detector/metrics.py",
    "../001-trail-detector-comparison/synthetic.py",
]


def _fingerprints():
    fps = {}
    for fn in _RESULT_FILES:
        p = os.path.normpath(os.path.join(HERE, fn))
        if os.path.exists(p):
            with open(p, "rb") as f:
                fps[fn] = hashlib.sha256(f.read()).hexdigest()
    return fps


def check_results(path):
    try:
        return _check_results_impl(path)
    except Exception as exc:
        return 1, f"results payload failed validation: {type(exc).__name__}: {exc}"


_PROBE_FLOAT_KEYS = {"runtime_s_mean", "runtime_s_p50", "runtime_s_p95",
                     "mean_angle_error_deg", "physical_trail_rate",
                     "synthetic_detection_rate_positives",
                     "synthetic_false_positive_rate_negatives"}


def _summaries_match(orig, recomputed, where):
    """Float-tolerant comparison of a metrics002 ``summarize`` dict."""
    if not isinstance(orig, dict):
        return False, f"{where}: summary must be an object"
    if set(orig.keys()) != set(recomputed.keys()):
        return False, f"{where}: summary keys differ: " \
                      f"{sorted(set(orig) ^ set(recomputed))!r}"
    for k, v in recomputed.items():
        o = orig[k]
        if k in _PROBE_FLOAT_KEYS:
            if v is None or o is None:
                if v != o:
                    return False, f"{where}.{k}: {o!r} != {v!r}"
            elif abs(v - o) > 1e-6 * max(1.0, abs(v), abs(o)):
                return False, f"{where}.{k}: {o!r} != {v!r}"
        elif o != v:
            return False, f"{where}.{k}: {o!r} != {v!r}"
    return True, ""


def _check_probe_impl(probe):
    """Validate a probe payload: size, explicit datasets/backends, exact
    ``(dataset, case_id)`` pairs once per backend, and recomputable summaries."""
    import run_probe_impl
    import metrics as metrics002

    if not isinstance(probe, dict):
        return 1, "probe must be an object"
    size = probe.get("size")
    if not isinstance(size, int) or size <= 0:
        return 1, f"probe.size must be a positive int, got {size!r}"

    datasets = probe.get("datasets")
    if not isinstance(datasets, dict):
        return 1, "probe.datasets must be an object"
    expected = {
        run_probe_impl.DATASET_002_BLIND: list(run_probe_impl._syn.BLIND_CASE_IDS),
        run_probe_impl.DATASET_AUDIT003: list(run_probe_impl._build_audit(size).keys()),
    }
    if set(datasets.keys()) != set(expected):
        return 1, f"probe.datasets keys differ: {sorted(set(datasets) ^ set(expected))!r}"
    for ds, ids in datasets.items():
        if list(ids) != list(expected[ds]):
            return 1, f"probe.datasets[{ds}] ids differ"

    backends = probe.get("backends")
    expected_backends = [run_probe_impl.BACKEND_BASELINE, run_probe_impl.BACKEND_PROBE]
    if backends != expected_backends:
        return 1, f"probe.backends must be exactly {expected_backends!r}, got {backends!r}"

    for sum_key, rows_key, backend in (
            ("baseline_summary", "baseline_rows", run_probe_impl.BACKEND_BASELINE),
            ("probe_summary", "probe_rows", run_probe_impl.BACKEND_PROBE)):
        rows = probe.get(rows_key)
        summary = probe.get(sum_key)
        if not isinstance(rows, list) or not rows:
            return 1, f"probe.{rows_key} must be a non-empty list"
        if not isinstance(summary, dict):
            return 1, f"probe.{sum_key} must be an object"

        seen = {}
        for r in rows:
            if not isinstance(r, dict):
                return 1, f"probe.{rows_key} row must be an object"
            if r.get("backend") != backend:
                return 1, f"probe.{rows_key} row backend {r.get('backend')!r} != {backend!r}"
            ds = r.get("dataset")
            if ds not in expected:
                return 1, f"probe.{rows_key} row has unknown dataset {ds!r}"
            cid = r.get("case_id")
            if cid not in expected[ds]:
                return 1, f"probe.{rows_key} row case {cid!r} not in dataset {ds}"
            key = (ds, cid)
            if key in seen:
                return 1, f"probe.{rows_key} duplicate pair {key!r}"
            seen[key] = r
        for ds, ids in expected.items():
            missing = [c for c in ids if (ds, c) not in seen]
            if missing:
                return 1, f"probe.{rows_key} missing {ds}: {missing!r}"

        # recompute summaries per dataset and compare (float-tolerated)
        for ds in expected:
            subset = [r for r in rows if r.get("dataset") == ds]
            ok, msg = _summaries_match(summary.get(ds), metrics002.summarize(subset),
                                       f"probe.{sum_key}[{ds}]")
            if not ok:
                return 1, msg

    return 0, "probe OK"


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
    probe = payload.get("probe")
    if not isinstance(meta, dict) or not isinstance(results, dict) \
            or not isinstance(summary, dict):
        return 1, "payload must contain meta/object, results/object, summary/object"

    has_profile = any(results.get(sk) for sk in SPLITS)
    has_probe = probe is not None
    if not has_profile and not has_probe:
        return 1, "payload has neither profile results nor a probe"

    # --- profile split validation (when present) ---
    for sk in SPLITS:
        rows = results.get(sk)
        if rows is None:
            continue
        if not isinstance(rows, list) or not rows:
            return 1, f"results.{sk} must be a non-empty list"
        expected_ids = list(SPLITS[sk]["cases"].keys())
        seen = {}
        for r in rows:
            if not isinstance(r, dict):
                return 1, f"results.{sk} row must be an object"
            cid = r.get("case_id")
            if cid in seen:
                return 1, f"results.{sk} duplicate case {cid!r}"
            seen[cid] = r
        if len(seen) != len(expected_ids):
            return 1, f"results.{sk} expected {len(expected_ids)} cases, got {len(seen)}"
        if set(seen) != set(expected_ids):
            return 1, f"results.{sk} case ids differ: missing=" \
                      f"{sorted(set(expected_ids) - set(seen))!r} extra=" \
                      f"{sorted(set(seen) - set(expected_ids))!r}"
        recomputed = _confusion_summary(rows)
        saved = summary.get(sk)
        if saved is None:
            return 1, f"summary.{sk} missing"
        if recomputed != saved:
            return 1, f"summary[{sk}] mismatch: saved={saved!r} recomputed={recomputed!r}"

    fps = meta.get("fingerprints")
    if not isinstance(fps, dict):
        return 1, "meta.fingerprints must be an object"
    current = _fingerprints()
    if set(fps.keys()) != set(current.keys()):
        return 1, f"meta.fingerprints keys differ: unexpected=" \
                  f"{sorted(set(fps) - set(current))!r} missing=" \
                  f"{sorted(set(current) - set(fps))!r}"
    for fn, h in current.items():
        if fps.get(fn) != h:
            return 1, f"fingerprint mismatch for {fn}: saved={fps.get(fn)} current={h}"

    # frozen config must match exactly (no blind tuning metadata).  Compare via
    # JSON round-trip so tuples serialised to lists on save compare equal.
    saved_cfg = json.loads(json.dumps(meta.get("config")))
    frozen_cfg = json.loads(json.dumps(CONFIG))
    if saved_cfg != frozen_cfg:
        return 1, "meta.config does not match frozen CONFIG"

    if meta.get("config_sha256") != _config_sha():
        return 1, "meta.config_sha256 mismatch"

    # --- probe validation (when present) ---
    probe_msg = ""
    if has_probe:
        code, msg = _check_probe_impl(probe)
        if code != 0:
            return 1, msg
        probe_msg = ", probe OK"

    if has_profile:
        parts = ", ".join(f"{sk}={len(results[sk])} rows" for sk in SPLITS if results.get(sk))
        return 0, f"results valid: {parts}, summary + fingerprints + config OK{probe_msg}"
    return 0, "results valid: probe OK, summary + fingerprints + config OK"


def _config_sha():
    return hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()


def _write_markdown(payload, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    meta = payload["meta"]
    L = ["# Spike TRAIL-02C — profil transverse (discriminateur de forme)", ""]
    L.append(f"- seeds: dev={meta['seed_dev']} blind={meta['seed_blind']}")
    L.append(f"- config SHA-256: `{meta['config_sha256']}`")
    L.append(f"- config (frozen): `{json.dumps(meta['config'], sort_keys=True)}`")
    L.append("")
    for sk in SPLITS:
        if sk not in payload["summary"]:
            continue
        L.append(f"## Split `{sk}` — matrice ridge/column/ambiguous")
        L.append("")
        s = payload["summary"][sk]
        L.append(f"- n={s['n_cases']} converged={s['n_converged']}")
        L.append(f"- ridge recall={s['ridge_recall']} "
                 f"(ridge->column={s['ridge_misclass_column']}, "
                 f"ridge->ambiguous={s['ridge_ambiguous']})")
        L.append(f"- column recall={s['column_recall']} "
                 f"(column->ridge={s['column_misclass_ridge']}, "
                 f"column->ambiguous={s['column_ambiguous']})")
        L.append(f"- ambiguous: GT={s['n_ambiguous_gt']} pred={s['n_ambiguous_pred']} "
                 f"correct={s['ambiguous_ok']} promoted={s['ambiguous_promoted']}")
        L.append(f"- runtime mean={s['runtime_s_mean']}s p50={s['runtime_s_p50']}s "
                 f"p95={s['runtime_s_p95']}s")
        L.append("")
        L.append("| case | kind | GT | pred | corr | pref | snr | conv | "
                 "sigma/width err |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for r in payload["results"][sk]:
            err = r.get("sigma_err", r.get("width_err"))
            err = f"{err:.3f}" if isinstance(err, (int, float)) else "-"
            L.append(f"| {r['case_id']} | {r.get('kind')} | {r['gt_label']} "
                     f"| {r['predicted']} | {r.get('correct')} | "
                     f"{r.get('preference', 0.0):+.3f} | {r.get('snr', 0):.1f} "
                     f"| {r.get('converged')} | {err} |")
        L.append("")
    if payload.get("probe"):
        L.append("## Sonde end-to-end (baseline 002 vs probe 003)")
        L.append("")
        L.append(f"- size={payload['probe']['size']} px")
        L.append(f"- baseline (002): {json.dumps(payload['probe']['baseline_summary'])}")
        L.append(f"- probe (003): {json.dumps(payload['probe']['probe_summary'])}")
        L.append("")
    md_path = os.path.join(out_dir, "results_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return md_path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Spike TRAIL-02C: transverse-profile shape discriminator.")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--full", action="store_true", help="probe at 256 px")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    ap.add_argument("--check-results", nargs="?", const=os.path.join(
        HERE, "results", "results_run.json"), default=None)
    args = ap.parse_args(argv)

    if args.check_results:
        code, msg = check_results(args.check_results)
        print(msg)
        return code

    results = {}
    summary = {}
    if args.dev or args.blind:
        for sk in SPLITS:
            if (args.dev and sk == "dev") or (args.blind and sk == "blind"):
                results[sk], summary[sk] = run_profile(sk, args.out_dir)
        if not results:
            results["dev"], summary["dev"] = run_profile("dev", args.out_dir)
            results["blind"], summary["blind"] = run_profile("blind", args.out_dir)

    meta = {
        "mission": "ZA-TRAIL-02C-TRANSVERSE-PROFILE-SPIKE-20261002",
        "seed_dev": DEV_SEED,
        "seed_blind": BLIND_SEED,
        "config": CONFIG,
        "config_sha256": _config_sha(),
        "fingerprints": _fingerprints(),
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    payload = {"meta": meta, "results": results, "summary": summary}

    if args.probe:
        size = 256 if args.full else 192
        payload["probe"] = run_probe(size, args.out_dir)

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "results_run.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    md_path = _write_markdown(payload, args.out_dir)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if summary:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
