"""Adapters wrapping the two acstools trail-detection backends for the spike.

Each adapter takes a plain 2D ``numpy`` image (plus a couple of documented
parameters) and returns a **spike common schema** dict.  No production code is
imported or modified; we only use the public acstools API.

Common result schema (per case, per backend)
--------------------------------------------
::

    {
        "backend": "acstools.satdet" | "acstools.findsat_mrt",
        "version": str,             # acstools.__version__
        "state": "ok" | "error" | "timeout",
        "runtime_s": float,         # wall clock around the backend call only
        "n_segments": int | None,   # satdet: segments returned (>=1 => "satellite")
        "n_sources": int | None,    # mrt: sources found in the radon domain
        "n_accepted": int | None,   # mrt: sources with status == 2 (accepted)
        "n_candidate": int | None,  # mrt: sources with status >= 1 (passed SNR+width)
        "status_counts": {0: int, 1: int, 2: int} | None,  # mrt status breakdown
        "angles_deg": [float],      # physical orientation per detected item
        "detected": bool,           # backend-level binary (see notes)
        "error": str | None,        # error reason when state != "ok"
        "rss_kb": int | None,       # filled by the runner (subprocess peak)
        "notes": [str],             # backend-specific caveats
    }

``detected`` semantics (documented, per backend):
  * satdet  -> ``len(segments) > 0`` (``detsat`` returns segments only when it
    concludes a satellite traversed the image).  Multiple segments from satdet
    describe **one** physical trail; they are *not* counted as several trails.
  * mrt     -> ``n_accepted > 0``, where "accepted" == status 2, matching
    acstools' own default ``mask_include_status=[2]`` and the diagnostic plot
    (status 2 = turquoise = accepted).  Status 1 means "passed SNR+width but
    failed persistence" and is reported separately as ``n_candidate``.

Both adapters disable *all* file outputs.  satdet necessarily writes temporary
FITS files (its public API reads from disk via ``glob``); those are created in a
private ``tempfile`` directory and removed afterwards.
"""

from __future__ import annotations

import glob
import logging
import os
import tempfile
import time
import warnings

import numpy as np

# acstools logs a lot at INFO; silence it so results/ are clean.
logging.getLogger("acstools").setLevel(logging.ERROR)
logging.getLogger("utils_findsat_mrt").setLevel(logging.ERROR)
logging.getLogger("findsat_mrt").setLevel(logging.ERROR)
logging.getLogger("photutils").setLevel(logging.ERROR)

try:
    import acstools
    _ACSTOOLS_VERSION = getattr(acstools, "__version__", None)
except Exception:  # pragma: no cover - environment guard
    acstools = None
    _ACSTOOLS_VERSION = None


def angle_from_endpoints(p0, p1):
    """Physical line orientation in [0, 180) degrees (same as synthetic module)."""
    dx = float(p1[0] - p0[0])
    dy = float(p1[1] - p0[1])
    return float(np.degrees(np.arctan2(dy, dx))) % 180.0


def _base_result(backend, version):
    return {
        "backend": backend,
        "version": version,
        "state": "ok",
        "runtime_s": 0.0,
        "n_segments": None,
        "n_sources": None,
        "n_accepted": None,
        "n_candidate": None,
        "status_counts": None,
        "angles_deg": [],
        "detected": False,
        "error": None,
        "rss_kb": None,
        "notes": [],
    }


# --------------------------------------------------------------------------- #
# Backend A: acstools.satdet (Probabilistic Hough Transform, historical)
# --------------------------------------------------------------------------- #
def run_satdet(image, size, seed, chips=(0,)):
    """Run ``acstools.satdet.detsat`` on a 2D image via temporary FITS files.

    Parameters
    ----------
    image : ndarray
        2D science image (already background-subtracted is NOT required; satdet
        does its own percentile rescale).
    size : int
        Linear image size, used only to scale the geometric parameters.
    seed : int
        Seed used only to name the temporary file (deterministic naming).

    Geometric feasibility adjustment (clearly signalled, ONE change):
    satdet is designed for full-frame ACS/WFC (~4096x2048).  Its default
    geometric parameters (``line_len=200``, ``small_edge=60``, ``line_gap=75``,
    ``buf=200``) are meaningless on a 128-256 px synthetic image, so they are
    rescaled to ``size``.  All detection thresholds (sigma, low/high threshold,
    percentile) keep their acstools defaults.
    """
    res = _base_result("acstools.satdet", _ACSTOOLS_VERSION)
    res["notes"].append(
        "geometric params (line_len/small_edge/line_gap/buf) rescaled to image "
        "size; this is a single documented feasibility adjustment. Hough angle "
        "filter excludes horizontal/vertical trails (round_angle % 90 == 0).")

    line_len = max(20, size // 2)
    line_gap = max(8, size // 4)
    small_edge = 20
    buf = max(8, size // 8)

    tmpdir = tempfile.mkdtemp(prefix="spike_satdet_")
    try:
        from astropy.io import fits
        from acstools.satdet import detsat

        fname = os.path.join(tmpdir, f"case_{seed}.fits")
        fits.PrimaryHDU(np.asarray(image, dtype=float)).writeto(fname)

        t0 = time.perf_counter()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                action="ignore",
                message=r".*is not a valid science extension.*",
                category=UserWarning)
            results, errors = detsat(
                glob.escape(fname), chips=list(chips), n_processes=1,
                sigma=2.0, low_thresh=0.1, h_thresh=0.5,
                line_len=line_len, small_edge=small_edge, line_gap=line_gap,
                percentile=(4.5, 93.0), buf=buf, plot=False, verbose=False)
        res["runtime_s"] = time.perf_counter() - t0

        if errors:
            first_key = next(iter(errors))
            res["state"] = "error"
            res["error"] = f"satdet error {first_key}: {errors[first_key]}"
            return res

        # results key is (filename, ext).  Collect all segments across chips.
        segs = []
        for (fil, ext), arr in results.items():
            arr = np.asarray(arr)
            if arr.size == 0:
                continue
            # arr shape (n, 2, 2): n segments of ((x0,y0),(x1,y1))
            for s in arr:
                p0 = (float(s[0][0]), float(s[0][1]))
                p1 = (float(s[1][0]), float(s[1][1]))
                segs.append((p0, p1))
        res["n_segments"] = len(segs)
        res["angles_deg"] = [angle_from_endpoints(p0, p1) for (p0, p1) in segs]
        res["detected"] = len(segs) > 0
        if len(segs) > 0:
            res["notes"].append(
                f"{len(segs)} segment(s) => satellite=True; segments describe "
                "one physical trail, not several trails.")
    except Exception as exc:  # pragma: no cover - error path
        res["state"] = "error"
        res["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    return res


# --------------------------------------------------------------------------- #
# Backend B: acstools.findsat_mrt.TrailFinder (Median Radon Transform)
# --------------------------------------------------------------------------- #
def run_mrt(image, size, theta_step, seed):
    """Run ``acstools.findsat_mrt.TrailFinder`` directly on a 2D array.

    Uses the public ``TrailFinder`` API (no ``WfcWrapper``, no private methods,
    no monkeypatching).  All file outputs are disabled.  ``processes=1`` for a
    stable, non-nested measurement.

    Documented preprocessing (standard, per acstools docstring example): the
    image median is subtracted before the transform, because the MRT error model
    assumes a zero-median (background-subtracted) input.

    Documented feasibility adjustments (single, clearly signalled):
      * ``buffer`` rescaled to the small image (default 250 targets full-frame).
      * ``theta`` passed explicitly (``np.arange(0, 180, theta_step)``) to bound
        the transform cost.
    ``min_length=25``, ``max_width=75``, ``threshold=5``,
    ``check_persistence=True``, ``min_persistence=0.5`` keep acstools defaults.
    """
    res = _base_result("acstools.findsat_mrt", _ACSTOOLS_VERSION)
    res["notes"].append(
        "median subtracted (standard MRT preprocessing); buffer rescaled to "
        "small image; theta explicit (step documented) to bound cost; "
        "processes=1; all file outputs disabled.")

    buffer = max(20, size // 4)
    theta = np.arange(0.0, 180.0, theta_step)

    try:
        from acstools.findsat_mrt import TrailFinder
        # acstools modules reset their own loggers to INFO at import time, so
        # re-assert the silence here (the submodule import is lazy).
        logging.getLogger("findsat_mrt").setLevel(logging.ERROR)
        logging.getLogger("utils_findsat_mrt").setLevel(logging.ERROR)

        sub = np.asarray(image, dtype=float) - np.nanmedian(image)

        # TemporaryDirectory guarantees cleanup (even on exception) so no
        # residual dir/files are left despite the (disabled) save_* options.
        with tempfile.TemporaryDirectory(prefix="spike_mrt_") as tmpdir:
            t0 = time.perf_counter()
            tf = TrailFinder(
                sub, processes=1, min_length=25, max_width=75, buffer=buffer,
                threshold=5, theta=theta,
                save_catalog=False, save_diagnostic=False, save_mrt=False,
                save_mask=False, output_dir=tmpdir)
            tf.run_mrt()
            tf.find_mrt_sources()
            tf.filter_sources()
            res["runtime_s"] = time.perf_counter() - t0

            if tf.source_list is None:
                res["n_sources"] = 0
                res["n_accepted"] = 0
                res["n_candidate"] = 0
                res["status_counts"] = {0: 0, 1: 0, 2: 0}
                res["detected"] = False
                return res

            statuses = [int(s) for s in tf.source_list["status"]]
            counts = {k: statuses.count(k) for k in (0, 1, 2)}
            res["n_sources"] = len(statuses)
            res["n_accepted"] = counts.get(2, 0)
            res["n_candidate"] = counts.get(1, 0) + counts.get(2, 0)
            res["status_counts"] = counts

            # Physical orientation from the full-streak endpoints (comparable
            # with satdet's segment orientation).
            angs = []
            for row in tf.source_list:
                p0, p1 = row["endpoints"]
                angs.append(angle_from_endpoints(p0, p1))
            res["angles_deg"] = angs

            # "accepted" == status 2, matching acstools default mask_include_status.
            res["detected"] = counts.get(2, 0) > 0
            if counts.get(1, 0) > 0:
                res["notes"].append(
                    "some sources reached status 1 (passed SNR+width, failed "
                    "persistence) but are NOT counted as accepted (status 2).")
    except Exception as exc:  # pragma: no cover - error path
        res["state"] = "error"
        res["error"] = f"{type(exc).__name__}: {exc}"
    return res


BACKENDS = {
    "satdet": {"label": "acstools.satdet", "run": run_satdet},
    "mrt": {"label": "acstools.findsat_mrt", "run": run_mrt},
}
