# ZeAnalyser Benchmark Protocol (budgets & performance gates)

**Status:** Normative — shared by TRAIL and CLOUD detector missions
**Version:** 1.0.0
**Applies to:** every detector prototype before promotion to product
**Date:** 2026-10-01

This document defines how performance budgets are measured and gated. It is
deliberately **relative** to a recorded baseline rather than inventing a
universal absolute time. A detector may not be promoted without a quantified
benchmark report attached to the reference profile below.

## 1. Reference profile (must be recorded, not assumed)

Every benchmark report MUST state, for the machine and environment actually
used:

- Sensor class: **2MP Seestar-like** (e.g. 1080×1920 CFA), nominal input size.
- Hardware: CPU model, core/thread count, total RAM.
- OS + version.
- Python version.
- Library versions actually used: numpy, astropy, photutils, scipy,
  scikit-image (and any detector-specific dependency, e.g. acstools).
- Worker count: bounded concurrency used (`n_processes`, pool size), explicitly
  ≤ CPU count and with **no nested multiprocessing**.
- Warmup: number of warmup iterations before timing.
- N: number of images per measurement run.
- Repetitions: number of independent repeats for p50/p95 stability.

## 2. Measured quantities

For a fixed reference profile and fixed input batch, the benchmark MUST report:

- Per-image time: **p50** and **p95**.
- Throughput: images/second.
- Peak RSS: parent process **and** per-worker.
- Memory slope: parent RSS growth per accumulated result (KiB/result), derived
  from a linear fit over the run's RSS samples.
- First vs last decile throughput: to detect a monotonic slowdown during a long
  batch (e.g. unbounded log/history growth).

## 3. Relative gates (measurable, no arbitrary universal time)

1. **Baseline regression gate.** Record the backend's own baseline (first
   run on the reference profile). A later change must not regress p50/p95 by
   more than **20%** without a written justification in the report.
2. **Monotonic-slowdown gate.** First→last decile throughput must not drop
   more than **20%** on a large batch; a larger drop indicates unbounded
   growth and blocks promotion.
3. **Parent memory slope gate.** Parent RSS slope per result must be
   **≤ a budget fixed explicitly before implementation** in the mission
   brief. The historical witness (~3.3 KiB/image) is informative only and
   MUST NOT be presented as universal.
4. **Peak worker RSS gate.** Peak per-worker RSS and p95 time receive a
   **candidate value in the prototype report** (not an invented promise) and
   are confirmed by Tristan before promotion.
5. **No-nested-pool gate.** CPU-first with bounded concurrency; nested
   multiprocessing is forbidden and is a hard rejection.

## 4. Scientific metric gates

These are **PROPOSED, TO CONFIRM** (not achieved, not claimed):

- Trails: net recall ≥ 95% on clear annotated trails; false positives ≤ 1%
  on representative negatives. Weak trails reported separately; sample sizes
  and uncertainties published.
- Transparency: transmission error on controlled injections; recall /
  false-positive / abstention rate on real data; intervals and sample sizes
  reported; the held-out set is kept untouched.

A promotion report MUST publish sample sizes, confidence intervals, and the
held-out set status. The contract blocks promotion without a quantified
budget in the benchmark report, even though it does not fix an arbitrary time
today.
