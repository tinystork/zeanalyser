"""Tests for the quality-first stacking plan ranking.

Covers the transparent quality score, deterministic intra-batch ordering,
centralized eligibility, numeric (non-lexical) metadata ordering, cohort
normalization, CSV column contract and mode fail-closed validation.
"""

import csv
import os
import random

import pytest

from zeanalyser.stack_plan import (
    CSV_COLUMNS,
    RANKING_MODE_METADATA,
    RANKING_MODE_QUALITY,
    generate_stacking_plan,
    write_stacking_plan_csv,
)


_HISTORICAL = [
    "order", "batch_id", "mount", "bortle", "telescope", "session_date",
    "filter", "exposure", "file_path", "ra", "dec",
]


def _row(path, *, snr=20.0, fwhm=2.0, ecc=0.3, starcount=200, sky_bg=100.0,
         sky_noise=10.0, bortle="3", telescope="T1", exposure=30, filt="L",
         date="2025-01-01T00:00:00", mount="ALTZ", **extra):
    r = {
        "mount": mount,
        "bortle": bortle,
        "telescope": telescope,
        "date_obs": date,
        "filter": filt,
        "exposure": exposure,
        "path": path,
        "snr": snr,
        "fwhm": fwhm,
        "ecc": ecc,
        "starcount": starcount,
        "sky_bg": sky_bg,
        "sky_noise": sky_noise,
    }
    r.update(extra)
    return r


# ---------------------------------------------------------------------------
# Score / formula / rank / reference
# ---------------------------------------------------------------------------
def test_quality_score_formula_and_rank():
    rows = [
        _row("/tmp/a.fits", snr=20.0, fwhm=2.0, ecc=0.3),  # best on all
        _row("/tmp/b.fits", snr=10.0, fwhm=4.0, ecc=0.7),  # worst on all
    ]
    plan = generate_stacking_plan(rows)
    by_path = {r["file_path"]: r for r in plan}

    # n=2: rank best = 0.75, rank worst = 0.25 for each metric
    assert by_path["/tmp/a.fits"]["quality_score"] == "75.0000"
    assert by_path["/tmp/b.fits"]["quality_score"] == "25.0000"
    assert by_path["/tmp/a.fits"]["quality_rank"] == "1"
    assert by_path["/tmp/b.fits"]["quality_rank"] == "2"
    assert by_path["/tmp/a.fits"]["quality_confidence"] == "1.0000"
    assert by_path["/tmp/a.fits"]["reference_candidate"] == "true"
    assert by_path["/tmp/b.fits"]["reference_candidate"] == "false"
    # first emitted row is the reference (best quality first)
    assert plan[0]["file_path"] == "/tmp/a.fits"
    assert plan[0]["order"] == 1


def test_quality_score_renormalized_when_metric_missing():
    # Only SNR present -> score renormalized over SNR alone, confidence 0.45.
    rows = [
        _row("/tmp/a.fits", snr=20.0, fwhm=None, ecc=None),
        _row("/tmp/b.fits", snr=10.0, fwhm=None, ecc=None),
    ]
    plan = generate_stacking_plan(rows)
    by_path = {r["file_path"]: r for r in plan}
    # rank 0.75 / 0.25 -> score = 100 * rank (renormalized)
    assert by_path["/tmp/a.fits"]["quality_score"] == "75.0000"
    assert by_path["/tmp/b.fits"]["quality_score"] == "25.0000"
    assert by_path["/tmp/a.fits"]["quality_confidence"] == "0.4500"
    assert by_path["/tmp/a.fits"]["fwhm"] == ""
    assert by_path["/tmp/a.fits"]["ecc"] == ""


def test_quality_score_empty_when_no_metric():
    rows = [
        _row("/tmp/a.fits", snr=None, fwhm=None, ecc=None, sky_bg=None,
             sky_noise=None, starcount=None),
        _row("/tmp/b.fits", snr=None, fwhm=None, ecc=None, sky_bg=None,
             sky_noise=None, starcount=None),
    ]
    plan = generate_stacking_plan(rows)
    for r in plan:
        assert r["quality_score"] == ""
        assert r["quality_confidence"] == "0.0000"


# ---------------------------------------------------------------------------
# Bortle tie-break: 1 before 9, Unknown last; sky_bg/noise before bortle
# ---------------------------------------------------------------------------
def test_bortle_tiebreak_numeric_unknown_last():
    rows = [
        _row("/tmp/b9.fits", bortle="9", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/b1.fits", bortle="1", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/unk.fits", bortle="Unknown", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
    ]
    plan = generate_stacking_plan(rows)
    order = [r["file_path"] for r in plan]
    assert order == ["/tmp/b1.fits", "/tmp/b9.fits", "/tmp/unk.fits"]
    assert plan[0]["reference_candidate"] == "true"


def test_sky_bg_and_noise_break_ties_before_bortle():
    # Same bortle, same score/confidence; sky_bg lower should win first.
    rows = [
        _row("/tmp/bg_hi.fits", sky_bg=500.0, sky_noise=50.0, snr=None,
             fwhm=None, ecc=None, starcount=None, bortle="3"),
        _row("/tmp/bg_lo.fits", sky_bg=100.0, sky_noise=10.0, snr=None,
             fwhm=None, ecc=None, starcount=None, bortle="3"),
    ]
    plan = generate_stacking_plan(rows)
    assert [r["file_path"] for r in plan] == ["/tmp/bg_lo.fits", "/tmp/bg_hi.fits"]


# ---------------------------------------------------------------------------
# Numeric exposure / bortle (never lexical)
# ---------------------------------------------------------------------------
def test_exposure_sorted_numerically_across_batches():
    rows = [
        _row("/tmp/e10.fits", exposure=10, telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/e120.fits", exposure=120, telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/e2.fits", exposure=2, telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/e30.fits", exposure=30, telescope="T1", date="2025-01-01T00:00:00"),
    ]
    # each exposure is its own batch (include_exposure_in_batch=True), and
    # sort by exposure ascending must be numeric (2,10,30,120 not 10,120,2,30).
    plan = generate_stacking_plan(
        rows,
        include_exposure_in_batch=True,
        sort_spec=[("exposure", False)],
        ranking_mode=RANKING_MODE_METADATA,
    )
    exposures = [r["exposure"] for r in plan]
    assert exposures == ["2", "10", "30", "120"]


def test_bortle_sorted_numerically_in_metadata_mode():
    rows = [
        _row("/tmp/b10.fits", bortle="10", telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/b2.fits", bortle="2", telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/b9.fits", bortle="9", telescope="T1", date="2025-01-01T00:00:00"),
    ]
    plan = generate_stacking_plan(
        rows,
        sort_spec=[("bortle", False)],
        ranking_mode=RANKING_MODE_METADATA,
    )
    assert [r["bortle"] for r in plan] == ["2", "9", "10"]


# ---------------------------------------------------------------------------
# Shuffle invariance
# ---------------------------------------------------------------------------
def test_shuffle_invariant_plan_order_and_score():
    rows = [
        _row(f"/tmp/img{i:02d}.fits", snr=random.uniform(5, 50),
             fwhm=random.uniform(1, 5), ecc=random.uniform(0, 1),
             starcount=random.randint(10, 500), sky_bg=random.uniform(50, 500),
             sky_noise=random.uniform(1, 50))
        for i in range(20)
    ]
    baseline = generate_stacking_plan(list(rows), sort_spec=[("exposure", False)])

    rng = random.Random(1234)
    for _ in range(10):
        shuffled = list(rows)
        rng.shuffle(shuffled)
        plan = generate_stacking_plan(shuffled, sort_spec=[("exposure", False)])
        assert [r["order"] for r in plan] == [r["order"] for r in baseline]
        assert [r["file_path"] for r in plan] == [r["file_path"] for r in baseline]
        assert [r["quality_score"] for r in plan] == [r["quality_score"] for r in baseline]
        assert plan == baseline


# ---------------------------------------------------------------------------
# Missing / non-finite / invalid metrics: fail-safe, confidence, sort after
# ---------------------------------------------------------------------------
def test_nonfinite_and_invalid_metrics_ignored():
    rows = [
        _row("/tmp/good.fits", snr=30.0, fwhm=1.5, ecc=0.2),
        _row("/tmp/bad.fits", snr=float("nan"), fwhm=float("inf"), ecc=-1.0),
        _row("/tmp/neg.fits", snr=-5.0, fwhm=-1.0, ecc=1.5),
    ]
    plan = generate_stacking_plan(rows)
    by_path = {r["file_path"]: r for r in plan}

    # only the good row has valid metrics -> confidence 1.0, rank 1
    assert by_path["/tmp/good.fits"]["quality_confidence"] == "1.0000"
    # non-finite metrics serialize as empty cells (auditable: not a number)
    assert by_path["/tmp/bad.fits"]["snr"] == ""
    assert by_path["/tmp/bad.fits"]["fwhm"] == ""
    # physically-invalid-but-finite metrics are still serialized raw
    # (auditable) but excluded from the score/confidence.
    assert by_path["/tmp/neg.fits"]["ecc"] == "1.5"
    assert by_path["/tmp/neg.fits"]["snr"] == "-5"
    assert by_path["/tmp/bad.fits"]["ecc"] == "-1"
    # invalid metrics are ignored by the score -> confidence 0, empty score
    assert by_path["/tmp/neg.fits"]["quality_confidence"] == "0.0000"
    assert by_path["/tmp/bad.fits"]["quality_confidence"] == "0.0000"
    assert by_path["/tmp/neg.fits"]["quality_score"] == ""
    assert by_path["/tmp/bad.fits"]["quality_score"] == ""
    # complete row (confidence 1) ranks before empty rows (confidence 0)
    assert plan[0]["file_path"] == "/tmp/good.fits"
    assert plan[0]["reference_candidate"] == "true"


def test_complete_rows_rank_before_incomplete():
    # Two rows with identical quality metrics but one missing sky_bg/noise
    # must still rank first because confidence is higher (0.45 vs 0.0... no,
    # both have full snr/fwhm/ecc -> same confidence).  Instead use one row
    # with metrics and one without: complete first.
    rows = [
        _row("/tmp/partial.fits", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/complete.fits", snr=20.0, fwhm=2.0, ecc=0.3),
    ]
    plan = generate_stacking_plan(rows)
    assert plan[0]["file_path"] == "/tmp/complete.fits"


# ---------------------------------------------------------------------------
# Cohort normalization: exposure separates cohorts even when out of batch_id
# ---------------------------------------------------------------------------
def test_cohort_exposure_separate_normalization():
    # Same batch (include_exposure_in_batch=False) but two exposures -> two
    # normalization cohorts.  A low-SNR 10s image must not be compared against
    # a high-SNR 30s image; within each cohort the best is rank 1.
    rows = [
        _row("/tmp/e10_hi.fits", exposure=10, snr=15.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e10_lo.fits", exposure=10, snr=5.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e30_hi.fits", exposure=30, snr=40.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e30_lo.fits", exposure=30, snr=20.0, fwhm=2.0, ecc=0.3),
    ]
    plan = generate_stacking_plan(rows, include_exposure_in_batch=False)
    by_path = {r["file_path"]: r for r in plan}

    # each exposure cohort has its own rank 1
    assert by_path["/tmp/e10_hi.fits"]["quality_rank"] == "1"
    assert by_path["/tmp/e30_hi.fits"]["quality_rank"] == "1"
    # quality_group differs between exposures
    assert by_path["/tmp/e10_hi.fits"]["quality_group"] != by_path["/tmp/e30_hi.fits"]["quality_group"]
    assert by_path["/tmp/e10_hi.fits"]["quality_group"] == '["T1","2025-01-01","L","10"]'
    assert by_path["/tmp/e30_hi.fits"]["quality_group"] == '["T1","2025-01-01","L","30"]'


def _batch_ids(plan):
    return [r["batch_id"] for r in plan]


def _assert_contiguous(plan):
    """Fail if any batch_id reappears after a different batch_id."""
    seen = set()
    prev = None
    for r in plan:
        bid = r["batch_id"]
        if bid != prev:
            assert bid not in seen, f"batch {bid!r} reappears non-contiguously"
            seen.add(bid)
        prev = bid


# ---------------------------------------------------------------------------
# Batches contiguous and metadata order stable
# ---------------------------------------------------------------------------
def test_batches_contiguous_and_metadata_order():
    rows = [
        _row("/tmp/t1a.fits", telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/t2a.fits", telescope="T2", date="2025-01-02T00:00:00"),
        _row("/tmp/t1b.fits", telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/t2b.fits", telescope="T2", date="2025-01-02T00:00:00"),
    ]
    plan = generate_stacking_plan(rows, sort_spec=[("telescope", False)])
    _assert_contiguous(plan)
    bids = _batch_ids(plan)
    # batch order: T1 block first, then T2 block
    first_t2 = next(i for i, r in enumerate(plan) if r["telescope"] == "T2")
    assert all(r["telescope"] == "T1" for r in plan[:first_t2])
    assert len(set(bids)) == 2


def test_batch_ids_contiguous_blocks():
    rows = [
        _row("/tmp/a.fits", telescope="T2"),
        _row("/tmp/b.fits", telescope="T1"),
        _row("/tmp/c.fits", telescope="T2"),
        _row("/tmp/d.fits", telescope="T1"),
    ]
    plan = generate_stacking_plan(rows, sort_spec=[("telescope", False)])
    _assert_contiguous(plan)
    assert len(_batch_ids(plan)) == 4


# ---------------------------------------------------------------------------
# Centralized eligibility: excludes pending / rejected / action non-kept
# ---------------------------------------------------------------------------
def test_eligibility_excludes_pending_rejected_nonkept():
    rows = [
        _row("/tmp/kept.fits", status="ok", action="kept"),
        _row("/tmp/pending.fits", status="ok", action="pending_snr_action"),
        _row("/tmp/rejected.fits", status="ok", action="kept", rejected_reason="low_snr"),
        _row("/tmp/notkept.fits", status="ok", action="moved_snr"),
        _row("/tmp/error.fits", status="error", action="kept"),
        # bare row without status/action is tolerated as ok
        _row("/tmp/bare.fits"),
    ]
    plan = generate_stacking_plan(rows)
    paths = {r["file_path"] for r in plan}
    assert "/tmp/kept.fits" in paths
    assert "/tmp/bare.fits" in paths
    assert "/tmp/pending.fits" not in paths
    assert "/tmp/rejected.fits" not in paths
    assert "/tmp/notkept.fits" not in paths
    assert "/tmp/error.fits" not in paths


def test_eligibility_action_must_be_kept_when_present():
    rows = [
        _row("/tmp/a.fits", action="kept"),
        _row("/tmp/b.fits", action="deleted_snr"),
    ]
    plan = generate_stacking_plan(rows)
    assert [r["file_path"] for r in plan] == ["/tmp/a.fits"]


# ---------------------------------------------------------------------------
# Metadata mode reproduces legacy ordering (with deterministic tie-break)
# ---------------------------------------------------------------------------
def test_metadata_mode_reproduces_legacy_order():
    rows = [
        _row("/tmp/z.fits", bortle="3"),
        _row("/tmp/a.fits", bortle="1"),
        _row("/tmp/m.fits", bortle="2"),
    ]
    plan = generate_stacking_plan(
        rows,
        sort_spec=[("bortle", False)],
        ranking_mode=RANKING_MODE_METADATA,
    )
    # metadata mode orders intra-batch by bortle ascending (numeric)
    assert [r["file_path"] for r in plan] == ["/tmp/a.fits", "/tmp/m.fits", "/tmp/z.fits"]
    assert all(r["ranking_mode"] == "metadata" for r in plan)


def test_metadata_mode_default_is_quality():
    rows = [
        _row("/tmp/a.fits", snr=10.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/b.fits", snr=30.0, fwhm=2.0, ecc=0.3),
    ]
    plan = generate_stacking_plan(rows)
    # default ranking_mode == quality -> best SNR first
    assert plan[0]["file_path"] == "/tmp/b.fits"
    assert all(r["ranking_mode"] == "quality" for r in plan)


def test_unknown_ranking_mode_fails_closed():
    with pytest.raises(ValueError):
        generate_stacking_plan([_row("/tmp/a.fits")], ranking_mode="bogus")


def test_legacy_alias_maps_to_metadata():
    plan = generate_stacking_plan(
        [_row("/tmp/a.fits", bortle="2"), _row("/tmp/b.fits", bortle="1")],
        sort_spec=[("bortle", False)],
        ranking_mode="legacy",
    )
    assert [r["file_path"] for r in plan] == ["/tmp/b.fits", "/tmp/a.fits"]
    assert plan[0]["ranking_mode"] == "metadata"


# ---------------------------------------------------------------------------
# CSV roundtrip: 11 historical columns first + new columns exact
# ---------------------------------------------------------------------------
def test_csv_columns_contract(tmp_path):
    rows = generate_stacking_plan([_row("/tmp/a.fits")])
    assert list(CSV_COLUMNS[:11]) == _HISTORICAL
    assert CSV_COLUMNS[11:] == [
        "snr", "fwhm", "ecc", "starcount", "sky_bg", "sky_noise",
        "quality_score", "quality_rank", "quality_confidence",
        "quality_group", "reference_candidate", "ranking_mode",
    ]

    csv_path = tmp_path / "plan.csv"
    write_stacking_plan_csv(str(csv_path), rows)

    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        assert header == CSV_COLUMNS
        data = list(reader)
    assert len(data) == len(rows)
    # historical columns byte-compatible: file_path matches
    assert data[0][header.index("file_path")] == "/tmp/a.fits"


def test_csv_roundtrip_historical_columns_in_head(tmp_path):
    # Use generated rows (not raw dicts) so the round-trip verifies the real
    # serialized content of the quality columns too.
    rows = generate_stacking_plan(
        [_row("/tmp/a.fits", snr=20.0, fwhm=2.0, ecc=0.3, ra="1.23", dec="-4.56")]
    )
    assert rows[0]["ra"] == "1.23"
    assert rows[0]["dec"] == "-4.56"
    assert rows[0]["snr"] == "20"
    csv_path = tmp_path / "plan.csv"
    write_stacking_plan_csv(str(csv_path), rows)
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        data = list(reader)
    assert header[:11] == _HISTORICAL
    assert header[0] == "order"
    assert header[1] == "batch_id"
    # content round-trips: historical file_path + new audit columns
    assert data[0]["file_path"] == "/tmp/a.fits"
    assert data[0]["quality_score"] == rows[0]["quality_score"]
    assert data[0]["quality_rank"] == "1"


# ---------------------------------------------------------------------------
# i18n placeholders FR/EN present
# ---------------------------------------------------------------------------
def test_i18n_placeholders_fr_en():
    from zeanalyser.zone import translations
    for lang in ("fr", "en"):
        t = translations[lang]
        for key in ("ranking_mode_label", "ranking_mode_quality",
                    "ranking_mode_metadata", "ranking_mode_quality_hint"):
            assert key in t, f"missing {key} in {lang}"


def test_i18n_hint_describes_percentile_not_reciprocal():
    from zeanalyser.zone import translations
    fr = translations["fr"]["ranking_mode_quality_hint"]
    en = translations["en"]["ranking_mode_quality_hint"]
    # must describe percentile ranks, not raw reciprocal 1/FWHM / 1/ECC
    assert "1/FWHM" not in fr and "1/ECC" not in fr
    assert "1/FWHM" not in en and "1/ECC" not in en
    assert "percentile" in fr.lower()
    assert "percentile" in en.lower()


# ---------------------------------------------------------------------------
# Rework-1 regressions
# ---------------------------------------------------------------------------
def _multi_batch_rows():
    """Four batches across two telescopes and two dates, with quality metrics."""
    return [
        _row("/tmp/t1d1a.fits", telescope="T1", date="2025-01-01T00:00:00", snr=30.0),
        _row("/tmp/t1d1b.fits", telescope="T1", date="2025-01-01T00:00:00", snr=10.0),
        _row("/tmp/t1d2a.fits", telescope="T1", date="2025-01-02T00:00:00", snr=25.0),
        _row("/tmp/t2d1a.fits", telescope="T2", date="2025-01-01T00:00:00", snr=40.0),
        _row("/tmp/t2d1b.fits", telescope="T2", date="2025-01-01T00:00:00", snr=12.0),
        _row("/tmp/t2d2a.fits", telescope="T2", date="2025-01-02T00:00:00", snr=20.0),
    ]


def test_batch_order_deterministic_empty_sort_spec():
    rows = _multi_batch_rows()
    baseline = generate_stacking_plan(list(rows))
    rng = random.Random(7)
    for _ in range(10):
        sh = list(rows)
        rng.shuffle(sh)
        plan = generate_stacking_plan(sh)
        assert _batch_ids(plan) == _batch_ids(baseline)
        assert [r["file_path"] for r in plan] == [r["file_path"] for r in baseline]
        assert plan == baseline


def test_batch_order_deterministic_partial_sort_spec():
    rows = _multi_batch_rows()
    baseline = generate_stacking_plan(list(rows), sort_spec=[("mount", False)])
    rng = random.Random(99)
    for _ in range(10):
        sh = list(rows)
        rng.shuffle(sh)
        plan = generate_stacking_plan(sh, sort_spec=[("mount", False)])
        assert _batch_ids(plan) == _batch_ids(baseline)
        assert plan == baseline


def test_numeric_missing_last_asc_and_desc_rows():
    rows = [
        _row("/tmp/u.fits", bortle="Unknown", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/3.fits", bortle="3", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/1.fits", bortle="1", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
        _row("/tmp/9.fits", bortle="9", snr=None, fwhm=None, ecc=None,
             sky_bg=None, sky_noise=None, starcount=None),
    ]
    asc = generate_stacking_plan(rows, sort_spec=[("bortle", False)],
                                 ranking_mode=RANKING_MODE_METADATA)
    assert [r["bortle"] for r in asc] == ["1", "3", "9", "Unknown"]
    desc = generate_stacking_plan(rows, sort_spec=[("bortle", True)],
                                  ranking_mode=RANKING_MODE_METADATA)
    # Unknown must remain last even in descending
    assert [r["bortle"] for r in desc] == ["9", "3", "1", "Unknown"]


def test_numeric_missing_last_desc_batches():
    # each telescope+date is a batch; bortle varies. In metadata descending,
    # the batch with Unknown bortle must still come last.
    rows = [
        _row("/tmp/a.fits", bortle="Unknown", telescope="T1", date="2025-01-01T00:00:00"),
        _row("/tmp/b.fits", bortle="3", telescope="T1", date="2025-01-02T00:00:00"),
        _row("/tmp/c.fits", bortle="5", telescope="T1", date="2025-01-03T00:00:00"),
    ]
    plan = generate_stacking_plan(rows, sort_spec=[("bortle", True)],
                                  ranking_mode=RANKING_MODE_METADATA)
    bortles = [r["bortle"] for r in plan]
    assert bortles[-1] == "Unknown"
    assert bortles[:-1] == ["5", "3"]


def test_quality_rank_is_per_cohort_not_per_batch():
    # One batch (telescope+date+filter identical) with two exposures -> two
    # cohorts -> two rank-1 rows, distinct quality_group. No global/batch rank.
    rows = [
        _row("/tmp/e10_hi.fits", exposure=10, snr=15.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e10_lo.fits", exposure=10, snr=5.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e30_hi.fits", exposure=30, snr=40.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/e30_lo.fits", exposure=30, snr=20.0, fwhm=2.0, ecc=0.3),
    ]
    plan = generate_stacking_plan(rows, include_exposure_in_batch=False)
    by_path = {r["file_path"]: r for r in plan}
    # two rank-1 rows (one per cohort), not a single global rank 1
    assert by_path["/tmp/e10_hi.fits"]["quality_rank"] == "1"
    assert by_path["/tmp/e30_hi.fits"]["quality_rank"] == "1"
    assert by_path["/tmp/e10_lo.fits"]["quality_rank"] == "2"
    assert by_path["/tmp/e30_lo.fits"]["quality_rank"] == "2"
    assert by_path["/tmp/e10_hi.fits"]["quality_group"] == '["T1","2025-01-01","L","10"]'
    assert by_path["/tmp/e30_hi.fits"]["quality_group"] == '["T1","2025-01-01","L","30"]'


def test_quality_group_unambiguous_with_underscores():
    from zeanalyser.stack_plan import _quality_group_id
    # components containing underscores must not collide
    g1 = _quality_group_id("T_1", "2025-01-01", "L", "30")
    g2 = _quality_group_id("T1", "2025-01-01", "L", "30")
    assert g1 != g2
    # empty component is preserved unambiguously
    g3 = _quality_group_id("T1", "", "", "30")
    assert g3 == '["T1","","","30"]'


def test_canonical_path_tiebreak_relative_and_dotdot():
    from zeanalyser.stack_plan import _canonical_path
    cwd = os.getcwd()
    # relative, ../ and absolute all canonicalize deterministically
    assert _canonical_path("a.fits") == os.path.normcase(os.path.abspath("a.fits"))
    assert _canonical_path("../a.fits") == os.path.normcase(os.path.abspath("../a.fits"))
    assert _canonical_path("~/a.fits") == os.path.normcase(
        os.path.abspath(os.path.expanduser("~/a.fits"))
    )
    # distinct inputs stay distinct
    assert _canonical_path("a.fits") != _canonical_path("../a.fits")
    assert _canonical_path("a.fits") != _canonical_path("b.fits")


def test_single_row_neutral_score_50():
    plan = generate_stacking_plan([_row("/tmp/solo.fits", snr=20.0, fwhm=2.0, ecc=0.3)])
    assert plan[0]["quality_score"] == "50.0000"
    assert plan[0]["quality_rank"] == "1"
    assert plan[0]["quality_confidence"] == "1.0000"
    assert plan[0]["reference_candidate"] == "true"


def test_all_equal_metrics_neutral_score_50_deterministic_path():
    rows = [
        _row("/tmp/z.fits", snr=20.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/a.fits", snr=20.0, fwhm=2.0, ecc=0.3),
        _row("/tmp/m.fits", snr=20.0, fwhm=2.0, ecc=0.3),
    ]
    plan = generate_stacking_plan(rows)
    # all equal -> neutral 50 for everyone
    assert {r["quality_score"] for r in plan} == {"50.0000"}
    # ties broken deterministically by canonical path (ascending)
    assert [r["file_path"] for r in plan] == ["/tmp/a.fits", "/tmp/m.fits", "/tmp/z.fits"]
    assert plan[0]["reference_candidate"] == "true"
