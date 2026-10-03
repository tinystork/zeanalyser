"""Utility to build stacking plans for ZeAnalyser.

This module exposes functions to generate CSV stacking plans from
analysis results.  Each result dict should at least contain the keys
``'mount'``, ``'bortle'``, ``'telescope'``, ``'date_obs'``, ``'filter'``,
``'exposure'`` and ``'path'``.  Results with ``status!='ok'`` are ignored.

The main function :func:`generate_stacking_plan` filters results
according to provided criteria, sorts them, groups them into batches and
returns a list of rows ready to be written to CSV.

The helper :func:`write_stacking_plan_csv` writes the CSV file.

╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Auteur  : Tinystork, seigneur des couteaux à beurre (aka Tristan Nauleau)       ║
║ Partenaire : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System ║
║              (aka ChatGPT, Grand Maître du ciselage de code)                    ║
║                                                                                 ║
║ Licence : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description :                                                                   ║
║   Ce programme a été forgé à la lueur des pixels et de la caféine,              ║
║   dans le but noble de transformer des nuages de photons en art                 ║
║   astronomique. Si vous l’utilisez, pensez à dire “merci”,                      ║
║   à lever les yeux vers le ciel, ou à citer Tinystork et J.A.R.V.I.S.           ║
║   (le karma des développeurs en dépend).                                        ║
║                                                                                 ║
║ Avertissement :                                                                 ║
║   Aucune IA ni aucun couteau à beurre n’a été blessé durant le                  ║
║   développement de ce code.                                                     ║
╚═════════════════════════════════════════════════════════════════════════════════╝


╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Author  : Tinystork, Lord of the Butter Knives (aka Tristan Nauleau)            ║
║ Partner : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System    ║
║           (aka ChatGPT, Grand Master of Code Chiseling)                         ║
║                                                                                 ║
║ License : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description:                                                                    ║
║   This program was forged under the sacred light of pixels and                  ║
║   caffeine, with the noble intent of turning clouds of photons into             ║
║   astronomical art. If you use it, please consider saying “thanks,”             ║
║   gazing at the stars, or crediting Tinystork and J.A.R.V.I.S. —                ║
║   developer karma depends on it.                                                ║
║                                                                                 ║
║ Disclaimer:                                                                     ║
║   No AIs or butter knives were harmed in the making of this code.               ║
╚════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations


from collections import defaultdict
import csv
import json
import math
import os
from typing import Dict, Iterable, List, Sequence, Tuple


FieldList = Dict[str, Sequence[str]]
SortSpec = Sequence[Tuple[str, bool]]  # (field, reverse)

# ---------------------------------------------------------------------------
# Ranking modes
# ---------------------------------------------------------------------------
RANKING_MODE_QUALITY = "quality"
RANKING_MODE_METADATA = "metadata"

# ``legacy`` is an accepted alias for ``metadata`` (kept for backward
# compatibility with callers that described the historical behaviour as
# "legacy").  Any other mode is rejected (fail-closed).
_RANKING_MODE_ALIASES = {
    RANKING_MODE_QUALITY: RANKING_MODE_QUALITY,
    RANKING_MODE_METADATA: RANKING_MODE_METADATA,
    "legacy": RANKING_MODE_METADATA,
}

# Quality-score weights.  SNR is higher-better; FWHM and ECC are lower-better.
# starcount is deliberately excluded from the score (strongly correlated with
# FWHM/SNR) and is only used as a tie-break/confidence signal.
_WEIGHT_SNR = 0.45
_WEIGHT_FWHM = 0.35
_WEIGHT_ECC = 0.20

# Metadata fields that must be ordered numerically, never as text.
_NUMERIC_FIELDS = ("bortle", "exposure")

# The 11 historical CSV columns, byte/order compatible, always at the head.
_HISTORICAL_COLUMNS = [
    "order",
    "batch_id",
    "mount",
    "bortle",
    "telescope",
    "session_date",
    "filter",
    "exposure",
    "file_path",
    "ra",
    "dec",
]

# Additive auditable columns appended after the historical columns.
_QUALITY_COLUMNS = [
    "snr",
    "fwhm",
    "ecc",
    "starcount",
    "sky_bg",
    "sky_noise",
    "quality_score",
    "quality_rank",
    "quality_confidence",
    "quality_group",
    "reference_candidate",
    "ranking_mode",
]

CSV_COLUMNS = _HISTORICAL_COLUMNS + _QUALITY_COLUMNS


def _canonical_path(path):
    """Pure deterministic canonical path used as a shuffle-invariant tie-break.

    ``normcase(abspath(expanduser(path)))`` — no filesystem access and no
    ``realpath``, so the result depends only on the string and the current
    working directory, never on what exists on disk.  ``normcase`` lowercases
    on Windows and is the identity on POSIX, giving the same portable
    case-insensitivity the rest of the toolchain assumes.
    """
    if path is None:
        path = ""
    return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))


def _quality_group_id(telescope, session_date, filt, exposure_key):
    """Unambiguous, auditable ``quality_group`` encoding.

    The four cohort components are serialized as a compact JSON array so any
    component may contain underscores or be empty without colliding (e.g.
    ``["T1_2","2025-01-01","L","30"]`` is never confusable with
    ``["T1","2_2025-01-01","L","30"]``).  ``batch_id`` is intentionally left
    as its historical underscore-joined form.
    """
    return json.dumps(
        [telescope, session_date, filt, exposure_key],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _to_float(value):
    """Return ``value`` as a finite float, or ``None`` if not numeric/finite."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _fmt_float(value):
    """Serialize a finite float to a stable decimal string, else ``''``.

    Up to 6 fractional digits; trailing zeros are trimmed (``30.0`` -> ``30``).
    Non-finite / non-numeric / missing values become the empty string so the
    CSV cell stays clean instead of ``nan``/``inf``.
    """
    f = _to_float(value)
    if f is None:
        return ""
    s = f"{f:.6f}"
    s = s.rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    return s


def _fmt_int(value):
    """Serialize a finite numeric value as an integer string, else ``''``."""
    f = _to_float(value)
    if f is None:
        return ""
    return str(int(round(f)))


def _canonical_exposure(exposure):
    """Canonical exposure key for cohort grouping and ``quality_group``.

    Numeric exposure values are normalised through ``_fmt_float`` so ``30``,
    ``30.0`` and ``"30"`` map to the same cohort.  Non-numeric values
    (``"N/A"``, missing) fall back to their raw string form.
    """
    f = _to_float(exposure)
    if f is not None:
        return _fmt_float(f)
    return str(exposure) if exposure is not None else ""


def _is_eligible(row: Dict) -> bool:
    """Centralized stacking eligibility.

    * ``status`` absent is tolerated as ``ok`` (bare rows / tests); a present
      non-``ok`` status is excluded.
    * if ``action`` is present it must be ``kept``.
    * any non-``None`` ``rejected_reason`` excludes the row.
    """
    if row.get("status", "ok") != "ok":
        return False
    action = row.get("action")
    if action is not None and action != "kept":
        return False
    if row.get("rejected_reason") is not None:
        return False
    return True


def _percentile_rank(values: List[float], value: float) -> float:
    """Robust percentile rank of ``value`` within ``values`` (avg of ties).

    Returns a value in ``[0, 1]``.  For ``n <= 1`` or all-equal values the
    neutral ``0.5`` is returned.
    """
    n = len(values)
    if n == 0:
        return 0.5
    less = 0
    equal = 0
    for v in values:
        if v < value:
            less += 1
        elif v == value:
            equal += 1
    return (less + 0.5 * equal) / n


def _numeric_dir_key(value, reverse: bool):
    """Direction-aware sort key for a numeric metadata field.

    Known finite values order ascending (``reverse=False``) or descending
    (``reverse=True``); missing / non-numeric values **always sort last**,
    regardless of direction.  The caller must sort this key ascending (no
    ``reverse`` flag), because the direction is already encoded in the value.
    """
    num = _to_float(value)
    if num is None:
        return (1, 0.0)
    return (0, -num if reverse else num)


def _row_field_value(row: Dict, field: str):
    """Raw value of a metadata sort field for an enriched row."""
    if field == "bortle":
        return row["bortle"]
    if field == "exposure":
        return row["exposure"]
    return row.get(field, "")


def _batch_representative_value(batch: List[Dict], field: str):
    """Deterministic representative of ``field`` across a batch.

    For numeric fields the minimum known value is used; for string fields the
    lexicographic minimum.  Using ``min`` makes the representative independent
    of the input order (shuffle-invariant).  Returns ``None`` / ``""`` when the
    field is absent from every row.
    """
    if field in _NUMERIC_FIELDS:
        nums = [_to_float(_row_field_value(row, field)) for row in batch]
        nums = [n for n in nums if n is not None]
        return min(nums) if nums else None
    strs = [_row_field_value(row, field) for row in batch]
    strs = [str(s) if s is not None else "" for s in strs]
    return min(strs) if strs else ""


def _quality_key(row: Dict):
    """Deterministic intra-batch ordering key (ascending -> best first).

    Order: confidence desc, score desc, valid sky_bg asc, valid sky_noise asc,
    known numeric Bortle asc (1 before 9, Unknown last), valid starcount desc,
    canonical normalized path asc.
    """
    conf = row["_confidence"]
    score = row["_score"]

    sky_bg = row["_sky_bg"]
    sky_noise = (
        row["_sky_noise"]
        if (row["_sky_noise"] is not None and row["_sky_noise"] >= 0)
        else None
    )
    starcount = (
        row["_starcount"]
        if (row["_starcount"] is not None and row["_starcount"] >= 0)
        else None
    )
    bortle_num = row["_bortle_num"]

    return (
        -conf,
        -score if score is not None else float("-inf"),
        sky_bg if sky_bg is not None else float("inf"),
        sky_noise if sky_noise is not None else float("inf"),
        (0, bortle_num) if bortle_num is not None else (1, 0.0),
        -starcount if starcount is not None else float("inf"),
        row["_path_norm"],
    )


def _sort_rows_metadata(rows: List[Dict], sort_spec: SortSpec) -> None:
    """Sort rows in-place by the metadata ``sort_spec`` (numeric-aware).

    A canonical-path tie-break is applied first (least significant) so the
    result is fully deterministic regardless of input order.  Numeric fields
    keep missing values last in both directions; string fields use the plain
    ``reverse`` flag.
    """
    rows.sort(key=lambda r: r["_path_norm"])
    for field, reverse in reversed(sort_spec):
        if field in _NUMERIC_FIELDS:
            rows.sort(
                key=lambda r, f=field: _numeric_dir_key(
                    _row_field_value(r, f), reverse
                )
            )
        else:
            rows.sort(
                key=lambda r, f=field: _row_field_value(r, f),
                reverse=reverse,
            )


def _sort_batches(batches: List[List[Dict]], sort_spec: SortSpec) -> None:
    """Sort batches in-place by the metadata ``sort_spec``.

    A canonical ``batch_id`` tie-break is applied first (least significant) so
    the batch order is deterministic even with an empty or partial
    ``sort_spec``.
    """
    batches.sort(key=lambda b: b[0]["batch_id"])
    for field, reverse in reversed(sort_spec):
        if field in _NUMERIC_FIELDS:
            batches.sort(
                key=lambda b, f=field: _numeric_dir_key(
                    _batch_representative_value(b, f), reverse
                )
            )
        else:
            batches.sort(
                key=lambda b, f=field: _batch_representative_value(b, f),
                reverse=reverse,
            )


def _normalize_ranking_mode(ranking_mode: str) -> str:
    """Return the canonical ranking mode, rejecting unknown modes (fail-closed)."""
    mode = _RANKING_MODE_ALIASES.get(ranking_mode, ranking_mode)
    if mode not in (RANKING_MODE_QUALITY, RANKING_MODE_METADATA):
        raise ValueError(
            f"Unknown ranking_mode {ranking_mode!r}; expected one of "
            f"('quality', 'metadata', 'legacy')"
        )
    return mode


def _extract_session_date(date_obs: str | None) -> str:
    """Return ``YYYY-MM-DD`` from DATE-OBS value or ``''`` if unavailable."""
    if not date_obs:
        return ""
    return str(date_obs).split("T")[0]


def generate_stacking_plan(
    results: Iterable[Dict],
    *,
    include_exposure_in_batch: bool = False,
    criteria: FieldList | None = None,
    sort_spec: SortSpec | None = None,
    ranking_mode: str = RANKING_MODE_QUALITY,
) -> List[Dict[str, str]]:
    """Build stacking plan rows from analysis results.

    Parameters
    ----------
    results : iterable of dict
        Analysis results.
    include_exposure_in_batch : bool, optional
        If ``True`` the exposure value is part of the ``batch_id``.
    criteria : dict, optional
        Mapping ``field -> allowed values``.  Values are sequences of
        strings.  ``None`` means no filtering on this field.
    sort_spec : sequence, optional
        List of ``(field, reverse)`` tuples.  This orders the *batches*; the
        order of images *inside* a batch is governed by ``ranking_mode``.
    ranking_mode : str, optional
        ``"quality"`` (default) orders each batch by the transparent quality
        score; ``"metadata"`` (alias ``"legacy"``) keeps the historical
        metadata ordering inside each batch.  Unknown modes raise
        ``ValueError``.

    Returns
    -------
    list of dict
        Each dict represents one CSV row.  The 11 historical columns come
        first (byte/order compatible), followed by the auditable quality
        columns ``snr``, ``fwhm``, ``ecc``, ``starcount``, ``sky_bg``,
        ``sky_noise``, ``quality_score``, ``quality_rank``,
        ``quality_confidence``, ``quality_group``, ``reference_candidate``
        and ``ranking_mode``.

    Notes
    -----
    ``quality_rank`` is the 1-based rank of the row **within its
    ``quality_group``** (the normalization cohort: telescope + session_date +
    filter + exposure), **not** within the batch.  A batch that spans several
    exposures therefore contains several independent rank-1 images; this is
    intentional (relative quality is only comparable within one cohort).
    ``reference_candidate`` is the only per-batch notion: ``true`` exactly for
    the first row of each batch in its final order.
    """
    criteria = criteria or {}
    sort_spec = list(sort_spec or [])
    mode = _normalize_ranking_mode(ranking_mode)

    # ---- 1. filter + enrich ----------------------------------------------
    enriched: List[Dict] = []
    for r in results:
        if not _is_eligible(r):
            continue

        mount = r.get("mount", "")
        bortle = str(r.get("bortle", ""))
        tele = r.get("telescope") or "Unknown"
        session_date = _extract_session_date(r.get("date_obs"))
        filt = r.get("filter", "")
        expo = r.get("exposure", "")
        expo_str = str(expo)
        path = r.get("path", "")
        ra = r.get("ra", "")
        dec = r.get("dec", "")

        values = {
            "mount": mount,
            "bortle": bortle,
            "telescope": tele,
            "session_date": session_date,
            "filter": filt,
            "exposure": expo_str,
            "ra": str(ra) if ra is not None else "",
            "dec": str(dec) if dec is not None else "",
        }

        skip = False
        for field, allowed in criteria.items():
            if allowed is None:
                continue
            if values.get(field) not in allowed:
                skip = True
                break
        if skip:
            continue

        enriched.append(
            {
                "mount": mount,
                "bortle": bortle,
                "telescope": tele,
                "session_date": session_date,
                "filter": filt,
                "exposure": expo_str,
                "file_path": path,
                "ra": str(ra) if ra is not None else "",
                "dec": str(dec) if dec is not None else "",
                # --- internal enrichment (not serialized directly) ---
                "_snr": _to_float(r.get("snr")),
                "_fwhm": _to_float(r.get("fwhm")),
                "_ecc": _to_float(r.get("ecc")),
                "_starcount": _to_float(r.get("starcount")),
                "_sky_bg": _to_float(r.get("sky_bg")),
                "_sky_noise": _to_float(r.get("sky_noise")),
                "_bortle_num": _to_float(bortle),
                "_exposure_key": _canonical_exposure(expo),
                "_path_norm": _canonical_path(path),
                "_score": None,
                "_confidence": 0.0,
                "_quality_rank": 0,
            }
        )

    if not enriched:
        return []

    # ---- 2. batch id + cohort --------------------------------------------
    batches_map: Dict[str, List[Dict]] = {}
    cohorts: Dict[Tuple, List[Dict]] = defaultdict(list)
    for row in enriched:
        batch_parts = [row["telescope"], row["session_date"], row["filter"]]
        if include_exposure_in_batch:
            batch_parts.append(row["exposure"])
        row["batch_id"] = "_".join(p for p in batch_parts if p)

        batches_map.setdefault(row["batch_id"], []).append(row)
        cohort_key = (
            row["telescope"],
            row["session_date"],
            row["filter"],
            row["_exposure_key"],
        )
        cohorts[cohort_key].append(row)
        row["_quality_group"] = _quality_group_id(
            row["telescope"],
            row["session_date"],
            row["filter"],
            row["_exposure_key"],
        )

    batches = list(batches_map.values())

    # ---- 3. quality score per normalization cohort ------------------------
    for cohort_rows in cohorts.values():
        snr_vals = sorted(
            r["_snr"] for r in cohort_rows if r["_snr"] is not None and r["_snr"] > 0
        )
        fwhm_vals = sorted(
            r["_fwhm"] for r in cohort_rows if r["_fwhm"] is not None and r["_fwhm"] > 0
        )
        ecc_vals = sorted(
            r["_ecc"]
            for r in cohort_rows
            if r["_ecc"] is not None and 0.0 <= r["_ecc"] <= 1.0
        )
        for r in cohort_rows:
            confidence = 0.0
            weighted = 0.0

            snr = r["_snr"]
            if snr is not None and snr > 0:
                confidence += _WEIGHT_SNR
                weighted += _WEIGHT_SNR * _percentile_rank(snr_vals, snr)

            fwhm = r["_fwhm"]
            if fwhm is not None and fwhm > 0:
                confidence += _WEIGHT_FWHM
                weighted += _WEIGHT_FWHM * (1.0 - _percentile_rank(fwhm_vals, fwhm))

            ecc = r["_ecc"]
            if ecc is not None and 0.0 <= ecc <= 1.0:
                confidence += _WEIGHT_ECC
                weighted += _WEIGHT_ECC * (1.0 - _percentile_rank(ecc_vals, ecc))

            r["_confidence"] = confidence
            # score renormalized over available metrics; None when no metric
            r["_score"] = (100.0 * weighted / confidence) if confidence > 0 else None

    # quality_rank: 1-based rank within the normalization cohort
    # (quality_group = telescope+session_date+filter+exposure), NOT within the
    # batch.  A batch spanning several exposures yields several rank-1 rows.
    # reference_candidate is the only per-batch notion (first row per batch).
    for cohort_rows in cohorts.values():
        for rank, r in enumerate(sorted(cohort_rows, key=_quality_key), start=1):
            r["_quality_rank"] = rank

    # ---- 4. batch order (metadata) ---------------------------------------
    _sort_batches(batches, sort_spec)

    # ---- 5. intra-batch order --------------------------------------------
    for batch in batches:
        if mode == RANKING_MODE_QUALITY:
            batch.sort(key=_quality_key)
        else:
            _sort_rows_metadata(batch, sort_spec)

    # ---- 6. serialize ----------------------------------------------------
    plan_rows: List[Dict[str, str]] = []
    order_idx = 1
    for batch in batches:
        for i, row in enumerate(batch):
            plan_rows.append(
                {
                    "order": order_idx,
                    "batch_id": row["batch_id"],
                    "mount": row["mount"],
                    "bortle": row["bortle"],
                    "telescope": row["telescope"],
                    "session_date": row["session_date"],
                    "filter": row["filter"],
                    "exposure": row["exposure"],
                    "file_path": row["file_path"],
                    "ra": row["ra"],
                    "dec": row["dec"],
                    "snr": _fmt_float(row["_snr"]),
                    "fwhm": _fmt_float(row["_fwhm"]),
                    "ecc": _fmt_float(row["_ecc"]),
                    "starcount": _fmt_int(row["_starcount"]),
                    "sky_bg": _fmt_float(row["_sky_bg"]),
                    "sky_noise": _fmt_float(row["_sky_noise"]),
                    "quality_score": (
                        f"{row['_score']:.4f}" if row["_score"] is not None else ""
                    ),
                    "quality_rank": str(row["_quality_rank"]),
                    "quality_confidence": f"{row['_confidence']:.4f}",
                    "quality_group": row["_quality_group"],
                    "reference_candidate": "true" if i == 0 else "false",
                    "ranking_mode": mode,
                }
            )
            order_idx += 1

    return plan_rows


def write_stacking_plan_csv(csv_path: str, rows: Iterable[Dict[str, str]]) -> None:
    """Write stacking plan rows to ``csv_path`` in UTF-8."""
    dirpath = os.path.dirname(csv_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    try:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            for row in rows:
                writer.writerow([row.get(col, "") for col in CSV_COLUMNS])
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot write to '{csv_path}'. File is in use or the directory is not writable."
        ) from exc

    return None
