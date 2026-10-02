"""Documentary contract tests for BASE-03A (contracts + corpus v1).

This test is intentionally dependency-free (stdlib only). It does NOT perform
full JSON Schema validation (that would require the ``jsonschema`` package,
which is deliberately not added and is NOT installed in this venv). Instead it:

- discovers the schemas and examples under ``docs/schemas/`` and
  ``docs/examples/``;
- parses every JSON file (asserting they are syntactically valid);
- locks ``$schema`` / ``$id`` / version / contract / states / enums and the
  structural invariants (required policies, required origin_preserved +
  scale/offset/matrix, coordinate-transform branches, image-prep color_mode
  coherence, sha256 / rel_path syntax including UNC);
- verifies cross-record invariants that JSON Schema cannot express (state-flag
  coherence, trail/transparency measure coherence, segment_count == len(segments),
  anti-leak grouping, ID uniqueness, double review, no orphans) — including
  explicit INVALID objects that the validation helpers must reject.

JSON Schema cannot express length equality (segment_count == len(segments)) or
group-reference integrity; those are deliberately checked here, in the helper,
not claimed to be in the schema. The real validator gate (if ever needed) is a
separate, opt-in step; this test is the lightweight lock that keeps the
documentation honest.
"""

from pathlib import Path
import json
import re
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "docs" / "schemas"
EXAMPLES_DIR = ROOT / "docs" / "examples"

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"

DETECTION_SCHEMA_ID = "urn:zeanalyser:contracts:detection-result:v1"
CORPUS_SCHEMA_ID = "urn:zeanalyser:contracts:corpus-manifest:v1"

DETECTION_STATES = {
    "measured_positive",
    "measured_negative",
    "indeterminate",
    "measurement_failure",
    "skipped",
    "unavailable",
}

DETECTION_CONTRACT = "zeanalyser.detection-result.v1"
CORPUS_CONTRACT = "zeanalyser.corpus-manifest.v1"

SPLITS = {"development", "validation", "holdout"}

COLOR_MODES = {"mono", "rgb", "cfa"}
BAYER_PATTERNS = {"RGGB", "BGGR", "GRBG", "GBRG"}
CFA_STRATEGIES = {"demosaic", "bin2x2", "superpixel"}

# Absolute-looking path prefixes: POSIX root, home, Windows drive, and UNC
# (one-or-more leading backslashes, e.g. \\server\share).
_ABS_PATH_RE = re.compile(r"^(/|[A-Za-z]:[\\/]|~|\\+)")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _json_files(directory: Path):
    return sorted(p for p in directory.glob("*.json") if p.is_file())


def _load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _all_strings(obj):
    """Yield every string in a nested JSON structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_strings(v)


def _is_number(value):
    """True for a real int/float, excluding bool (bool is not a scientific number)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value):
    """True for a real int, excluding bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _detection_examples():
    return [
        p for p in _json_files(EXAMPLES_DIR)
        if _load(p).get("contract") == DETECTION_CONTRACT
    ]


def _corpus_examples():
    return [
        p for p in _json_files(EXAMPLES_DIR)
        if _load(p).get("contract") == CORPUS_CONTRACT
    ]


def _is_iso_datetime(value):
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Cross-record validation helpers (used on examples AND on invalid objects)
# ---------------------------------------------------------------------------

def _check_state_flags(record):
    """Return a list of error strings for state/flag coherence."""
    errs = []
    state = record.get("state")
    completed = record.get("analysis_completed")
    backend = record.get("backend_available")
    domain = record.get("domain_covered")
    error = record.get("error")
    reason = record.get("reason")

    if state in ("measured_positive", "measured_negative"):
        if completed is not True:
            errs.append(f"{state} requires analysis_completed true")
        if backend is not True:
            errs.append(f"{state} requires backend_available true")
        if domain is not True:
            errs.append(f"{state} requires domain_covered true")
        if error is not None:
            errs.append(f"{state} requires error null")
    elif state == "measurement_failure":
        if completed is not False:
            errs.append("measurement_failure requires analysis_completed false")
        if not isinstance(error, dict):
            errs.append("measurement_failure requires non-null error object")
    elif state == "skipped":
        if completed is not False:
            errs.append("skipped requires analysis_completed false")
        if not isinstance(reason, dict):
            errs.append("skipped requires non-null reason object")
    elif state == "unavailable":
        if completed is not False:
            errs.append("unavailable requires analysis_completed false")
        if backend is not False:
            errs.append("unavailable requires backend_available false")
        if not isinstance(reason, dict):
            errs.append("unavailable requires non-null reason object")
    elif state == "indeterminate":
        if not isinstance(reason, dict):
            errs.append("indeterminate requires non-null reason object")
    return errs


def _check_trail_measures(record):
    """Return error strings for trail measure/state coherence."""
    errs = []
    if record.get("detector", {}).get("family") != "trail":
        return errs
    meas = record.get("measurements", {})
    state = record.get("state")

    seg_count = meas.get("segment_count")
    segments = meas.get("segments")
    physical = meas.get("physical_trail_count")

    # segment_count must be a real int and equal len(segments) (JSON Schema
    # cannot express this length equality; it is checked here).
    if not _is_int(seg_count):
        errs.append("segment_count must be an integer")
    if not isinstance(segments, list):
        errs.append("segments must be a list")
    else:
        if _is_int(seg_count) and seg_count != len(segments):
            errs.append(f"segment_count {seg_count} != len(segments) {len(segments)}")
        # duplicate segment ids forbidden
        ids = [s.get("segment_id") for s in segments if isinstance(s, dict)]
        if len(ids) != len(set(ids)):
            errs.append("duplicate segment_id in segments")
        # trail_group segment_ids must reference existing segments
        known = set(ids)
        for g in meas.get("trail_groups", []) or []:
            if not isinstance(g, dict):
                continue
            for sid in g.get("segment_ids", []) or []:
                if sid not in known:
                    errs.append(f"trail_group references unknown segment {sid}")

    if state == "measured_positive":
        if not _is_int(seg_count) or seg_count < 1:
            errs.append("trail positive requires segment_count >= 1")
        if not isinstance(segments, list) or len(segments) < 1:
            errs.append("trail positive requires non-empty segments")
        if physical is not None and (not _is_int(physical) or physical < 1):
            errs.append("trail positive physical_trail_count must be null or >= 1")
    elif state == "measured_negative":
        if seg_count != 0:
            errs.append("trail negative requires segment_count == 0")
        if segments != []:
            errs.append("trail negative requires empty segments")
        if physical not in (0, None):
            errs.append("trail negative requires physical_trail_count 0 or null")
    return errs


def _check_transparency_measures(record):
    """Return error strings for transparency measure/state coherence."""
    errs = []
    if record.get("detector", {}).get("family") != "transparency":
        return errs
    meas = record.get("measurements", {})
    state = record.get("state")

    rt = meas.get("relative_transmission")
    te = meas.get("transmission_error")
    if rt is not None and (not _is_number(rt) or rt < 0):
        errs.append("relative_transmission must be null or a number >= 0 (bool excluded)")
    if te is not None and (not _is_number(te) or te < 0):
        errs.append("transmission_error must be null or a number >= 0 (bool excluded)")
    fr = meas.get("star_fraction_recovered")
    if fr is not None and (not _is_number(fr) or not (0 <= fr <= 1)):
        errs.append("star_fraction_recovered must be null or a number in [0,1]")
    sc = meas.get("star_count_used")
    if sc is not None and not _is_int(sc) or sc is not None and sc < 0:
        errs.append("star_count_used must be null or a non-negative integer")
    if rt is not None and not isinstance(meas.get("reference"), dict):
        errs.append("reference must be a non-null object when relative_transmission is non-null")

    if state == "measured_positive":
        if meas.get("veil_state") not in ("probable_veil", "unattributed_degradation"):
            errs.append("transparency positive requires veil_state probable_veil|unattributed_degradation")
    elif state == "measured_negative":
        if meas.get("veil_state") != "clear":
            errs.append("transparency negative requires veil_state == clear")
    return errs


def _check_coordinate_transform(record):
    """Return error strings for coordinate-transform coherence."""
    errs = []
    ct = record.get("coordinate_transform", {})
    if "origin_preserved" not in ct:
        errs.append("coordinate_transform.origin_preserved is required")
    elif not isinstance(ct["origin_preserved"], bool):
        errs.append("origin_preserved must be boolean")

    # scale/offset/matrix are ALWAYS present (active vector/matrix or null).
    for field in ("scale", "offset", "matrix"):
        if field not in ct:
            errs.append(f"coordinate_transform.{field} must always be present")

    method = ct.get("method")
    scale = ct.get("scale")
    offset = ct.get("offset")
    matrix = ct.get("matrix")

    if method == "scale_offset":
        if not (isinstance(scale, list) and len(scale) == 2):
            errs.append("scale_offset requires scale length 2")
        if not (isinstance(offset, list) and len(offset) == 2):
            errs.append("scale_offset requires offset length 2")
        if matrix is not None:
            errs.append("scale_offset requires matrix null")
    elif method == "affine":
        if not (isinstance(matrix, list) and len(matrix) == 2
                and all(isinstance(row, list) and len(row) == 3 for row in matrix)):
            errs.append("affine requires 2x3 matrix")
        if scale is not None or offset is not None:
            errs.append("affine requires scale and offset null")
    return errs


def _check_image_prep(record):
    """Return error strings for image-prep coherence."""
    errs = []
    prep = record.get("input", {}).get("image_prep", {})
    required_policies = ["nan_inf_policy", "saturation_policy",
                         "invalid_pixel_policy", "background_policy"]
    for p in required_policies:
        if not isinstance(prep.get(p), str) or prep[p] == "":
            errs.append(f"image_prep.{p} required non-empty")

    mode = prep.get("color_mode")
    bayer = prep.get("bayer_pattern")
    cfa_strategy = prep.get("cfa_strategy")
    lum = prep.get("rgb_luminance_formula")

    if mode == "mono":
        if bayer is not None or cfa_strategy is not None or lum is not None:
            errs.append("mono must not require cfa/rgb-specific fields")
    elif mode == "rgb":
        if not isinstance(lum, str) or lum == "":
            errs.append("rgb requires non-empty rgb_luminance_formula")
        if bayer is not None or cfa_strategy is not None:
            errs.append("rgb must not set bayer_pattern/cfa_strategy")
    elif mode == "cfa":
        if bayer not in BAYER_PATTERNS:
            errs.append("cfa requires non-null bayer_pattern")
        if cfa_strategy not in CFA_STRATEGIES:
            errs.append("cfa requires declared cfa_strategy")
        if lum is not None:
            errs.append("cfa must not set rgb_luminance_formula")
    return errs


def _check_rel_paths(record):
    """Return error strings for absolute paths in rel_path fields."""
    errs = []
    rel_path = record.get("input", {}).get("rel_path")
    if isinstance(rel_path, str) and _ABS_PATH_RE.match(rel_path):
        errs.append(f"rel_path is absolute: {rel_path!r}")
    sha = record.get("input", {}).get("sha256")
    if isinstance(sha, str) and not _SHA256_RE.match(sha):
        errs.append("sha256 must be 64 hex chars")
    return errs


# ---------------------------------------------------------------------------
# Schema-level locks
# ---------------------------------------------------------------------------

def test_schemas_exist_and_are_valid_json():
    schemas = _json_files(SCHEMAS_DIR)
    assert schemas, "no schemas found under docs/schemas/"
    for path in schemas:
        data = _load(path)  # raises on invalid JSON
        assert isinstance(data, dict)


def test_schemas_lock_meta_schema_and_ids():
    by_id = {}
    for path in _json_files(SCHEMAS_DIR):
        data = _load(path)
        assert data.get("$schema") == DRAFT_2020_12, f"{path.name}: wrong $schema"
        assert data.get("$id"), f"{path.name}: missing $id"
        by_id[data["$id"]] = path.name
    assert DETECTION_SCHEMA_ID in by_id
    assert CORPUS_SCHEMA_ID in by_id


def test_detection_schema_locks_states_and_version():
    data = _load(SCHEMAS_DIR / "detection-result-v1.schema.json")
    props = data.get("properties", {})
    assert props["schema_version"]["const"] == "1.0.0"
    assert props["contract"]["const"] == DETECTION_CONTRACT
    assert set(props["state"]["enum"]) == DETECTION_STATES
    assert "detected" not in props
    # structural locks the rework requires
    image_prep = data["$defs"]["imagePrep"]
    assert "nan_inf_policy" in image_prep["required"]
    assert "saturation_policy" in image_prep["required"]
    assert "invalid_pixel_policy" in image_prep["required"]
    assert "background_policy" in image_prep["required"]
    assert "cfa_strategy" in image_prep["properties"]
    ct = data["$defs"]["coordinateTransform"]
    assert "origin_preserved" in ct["required"]
    assert "scale" in ct["required"]
    assert "offset" in ct["required"]
    assert "matrix" in ct["required"]
    assert "matrix2x3" in data["$defs"]
    # transparency reference non-null when transmission is numeric (structural lock)
    tm = data["$defs"]["transparencyMeasurements"]
    ref_then = tm["allOf"][0]["then"]
    assert "reference" in ref_then.get("properties", {})
    assert ref_then["properties"]["reference"].get("$ref") == "#/$defs/transparencyReference"


def test_corpus_schema_locks_splits_reviewed_and_version():
    data = _load(SCHEMAS_DIR / "corpus-manifest-v1.schema.json")
    props = data.get("properties", {})
    assert props["schema_version"]["const"] == "1.0.0"
    assert props["contract"]["const"] == CORPUS_CONTRACT
    defs = data.get("$defs", {})
    assert set(defs["split"]["properties"]["split_id"]["enum"]) == SPLITS
    assert "reviewed" in defs["annotation"]["required"]


# ---------------------------------------------------------------------------
# Example-level locks
# ---------------------------------------------------------------------------

def test_examples_exist_and_are_valid_json():
    examples = _json_files(EXAMPLES_DIR)
    assert examples, "no examples found under docs/examples/"
    for path in examples:
        data = _load(path)
        assert isinstance(data, dict)


def test_detection_examples_lock_schema_version_contract_state():
    examples = _detection_examples()
    assert examples, "no detection examples found"
    for path in examples:
        data = _load(path)
        assert data.get("$schema") == DETECTION_SCHEMA_ID, path.name
        assert data.get("schema_version") == "1.0.0", path.name
        assert data.get("contract") == DETECTION_CONTRACT, path.name
        assert data["state"] in DETECTION_STATES, path.name
        assert data["detector"]["family"] in {"trail", "transparency"}, path.name
        assert isinstance(data["result_id"], str) and data["result_id"], path.name


def test_detection_examples_state_flags_coherent():
    for path in _detection_examples():
        data = _load(path)
        errs = _check_state_flags(data)
        assert not errs, f"{path.name}: {errs}"


def test_detection_examples_trail_measures_coherent():
    for path in _detection_examples():
        data = _load(path)
        errs = _check_trail_measures(data)
        assert not errs, f"{path.name}: {errs}"


def test_detection_examples_transparency_measures_coherent():
    for path in _detection_examples():
        data = _load(path)
        errs = _check_transparency_measures(data)
        assert not errs, f"{path.name}: {errs}"


def test_detection_examples_coordinate_transform_coherent():
    methods_seen = set()
    for path in _detection_examples():
        data = _load(path)
        errs = _check_coordinate_transform(data)
        assert not errs, f"{path.name}: {errs}"
        methods_seen.add(data["coordinate_transform"]["method"])
    assert "scale_offset" in methods_seen, "no scale_offset example"
    assert "affine" in methods_seen, "no affine example"


def test_detection_examples_image_prep_coherent():
    for path in _detection_examples():
        data = _load(path)
        errs = _check_image_prep(data)
        assert not errs, f"{path.name}: {errs}"


def test_detection_examples_rel_path_and_sha_syntax():
    for path in _detection_examples():
        data = _load(path)
        errs = _check_rel_paths(data)
        assert not errs, f"{path.name}: {errs}"


def test_detection_examples_timestamp_is_datetime():
    for path in _detection_examples():
        data = _load(path)
        ts = data.get("provenance", {}).get("timestamp")
        assert _is_iso_datetime(ts), f"{path.name}: timestamp not date-time: {ts!r}"


def test_no_boolean_detected_field_anywhere():
    for path in _json_files(EXAMPLES_DIR):
        data = _load(path)
        assert "detected" not in data, path.name
        assert "has_trails" not in data, path.name


def test_no_absolute_paths_or_secrets_anywhere():
    for path in _json_files(EXAMPLES_DIR):
        data = _load(path)
        for s in _all_strings(data):
            assert not _ABS_PATH_RE.match(s), f"{path.name}: absolute path {s!r}"
            assert "password" not in s.lower()
            assert "api_key" not in s.lower()
            assert "secret" not in s.lower()


# ---------------------------------------------------------------------------
# Corpus example cross-record invariants
# ---------------------------------------------------------------------------

def _manifest_index(manifest):
    """Build an index of a corpus manifest and return (index, errors)."""
    errs = []
    session_split = {}
    target_split = {}
    sessions_by_id = {}
    targets_by_id = {}
    images = {}
    image_split = {}

    for sess in manifest.get("sessions", []):
        sid = sess["session_id"]
        if sid in sessions_by_id:
            errs.append(f"duplicate session_id {sid}")
        sessions_by_id[sid] = sess
        session_split[sid] = sess["split"]
        for img in sess.get("image_ids", []):
            iid = img["image_id"]
            if iid in images:
                errs.append(f"duplicate image_id {iid}")
            images[iid] = img
            image_split[iid] = sess["split"]
            if img.get("color_mode") == "cfa" and img.get("bayer_pattern") not in BAYER_PATTERNS:
                errs.append(f"cfa image {iid} missing bayer_pattern")

    for tgt in manifest.get("targets", []):
        tid = tgt["target_id"]
        if tid in targets_by_id:
            errs.append(f"duplicate target_id {tid}")
        targets_by_id[tid] = tgt
        target_split[tid] = tgt["split"]

    split_ids = set()
    for split_name, split in manifest.get("splits", {}).items():
        assert split["split_id"] == split_name
        split_ids.add(split_name)
        for sid in split.get("session_ids", []):
            if session_split.get(sid) != split_name:
                errs.append(f"session {sid} split mismatch")
        for tid in split.get("target_ids", []):
            if target_split.get(tid) != split_name:
                errs.append(f"target {tid} split mismatch")

    for sid, sp in session_split.items():
        if sid not in manifest.get("splits", {}).get(sp, {}).get("session_ids", []):
            errs.append(f"session {sid} not listed in its split {sp}")
    for tid, sp in target_split.items():
        if tid not in manifest.get("splits", {}).get(sp, {}).get("target_ids", []):
            errs.append(f"target {tid} not listed in its split {sp}")

    for tgt in manifest.get("targets", []):
        expected = {sid for sid, s in sessions_by_id.items()
                    if s.get("target_id") == tgt["target_id"]}
        actual = set(tgt.get("session_ids", []))
        if expected != actual:
            errs.append(f"target {tgt['target_id']} session_ids {sorted(actual)} != {sorted(expected)}")

    tic = manifest.get("corpus", {}).get("target_image_count", {})
    if _is_int(tic.get("min")) and _is_int(tic.get("max")):
        if tic["min"] > tic["max"]:
            errs.append("target_image_count min > max")

    return {
        "session_split": session_split,
        "target_split": target_split,
        "images": images,
        "image_split": image_split,
    }, errs


def test_corpus_example_lock_and_anti_leak():
    manifests = _corpus_examples()
    assert manifests, "no corpus manifest example found"
    for path in manifests:
        data = _load(path)
        assert data.get("$schema") == CORPUS_SCHEMA_ID, path.name
        assert data.get("schema_version") == "1.0.0", path.name
        idx, errs = _manifest_index(data)
        assert not errs, f"{path.name}: {errs}"


def test_corpus_annotations_reference_known_images_and_kinds():
    for path in _corpus_examples():
        data = _load(path)
        idx, _ = _manifest_index(data)
        known_images = idx["images"]
        ann_ids = set()
        for ann in data["annotations"]:
            assert ann["image_id"] in known_images, path.name
            assert ann["kind"] in {"trail", "transparency"}, path.name
            assert ann["label"] in {"present", "absent", "uncertain", "not_applicable"}, path.name
            assert ann["annotation_id"] not in ann_ids, f"{path.name}: duplicate annotation_id"
            ann_ids.add(ann["annotation_id"])
            assert isinstance(ann.get("reviewed"), bool), f"{path.name}: reviewed missing/not bool"


def test_corpus_double_review_policy():
    """validation/holdout annotations must be reviewed; development may be false."""
    for path in _corpus_examples():
        data = _load(path)
        idx, _ = _manifest_index(data)
        image_split = idx["image_split"]
        for ann in data["annotations"]:
            split = image_split[ann["image_id"]]
            if split in ("validation", "holdout"):
                assert ann["reviewed"] is True, (
                    f"{path.name}: {ann['annotation_id']} in {split} not reviewed"
                )


# ---------------------------------------------------------------------------
# Explicit invalid objects: the cross-record helpers must reject them
# ---------------------------------------------------------------------------

def test_invalid_negative_missing_proof_rejected():
    bad = _load(_detection_examples()[0])
    bad["state"] = "measured_negative"
    bad["analysis_completed"] = False
    assert _check_state_flags(bad)


def test_invalid_failure_without_error_rejected():
    bad = _load(_detection_examples()[0])
    bad["state"] = "measurement_failure"
    bad["analysis_completed"] = False
    bad["error"] = None
    assert _check_state_flags(bad)


def test_invalid_trail_negative_nonzero_segments_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-negative.json")
    bad["measurements"]["segment_count"] = 1
    assert _check_trail_measures(bad)


def test_invalid_trail_count_mismatch_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-positive.json")
    bad["measurements"]["segment_count"] = 99
    assert _check_trail_measures(bad)


def test_invalid_trail_group_unknown_segment_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-positive.json")
    bad["measurements"]["trail_groups"] = [
        {"group_id": "g1", "segment_ids": ["nope"], "physical_trail_count": 1}
    ]
    assert _check_trail_measures(bad)


def test_invalid_transparency_negative_wrong_veil_rejected():
    bad = _load(EXAMPLES_DIR / "transparency-measured-negative.json")
    bad["measurements"]["veil_state"] = "probable_veil"
    assert _check_transparency_measures(bad)


def test_invalid_transparency_numeric_transmission_null_reference_rejected():
    bad = _load(EXAMPLES_DIR / "transparency-measured-negative.json")
    bad["measurements"]["relative_transmission"] = 1.02
    bad["measurements"]["reference"] = None
    assert _check_transparency_measures(bad)


def test_invalid_transparency_bool_transmission_rejected():
    bad = _load(EXAMPLES_DIR / "transparency-measured-negative.json")
    bad["measurements"]["relative_transmission"] = True
    assert _check_transparency_measures(bad)


def test_invalid_affine_with_scale_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-positive.json")
    bad["coordinate_transform"]["scale"] = [1.0, 1.0]
    assert _check_coordinate_transform(bad)


def test_invalid_transform_inactive_field_omitted_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-positive.json")
    # affine method: matrix active, but scale/offset omitted entirely
    del bad["coordinate_transform"]["scale"]
    assert _check_coordinate_transform(bad)


def test_invalid_transform_active_field_absent_rejected():
    bad = _load(EXAMPLES_DIR / "trail-measured-negative.json")
    # scale_offset method: scale/offset active, but matrix omitted entirely
    del bad["coordinate_transform"]["matrix"]
    assert _check_coordinate_transform(bad)


def test_invalid_absolute_rel_path_rejected():
    bad = _load(_detection_examples()[0])
    bad["input"]["rel_path"] = "/home/user/img.fits"
    assert _check_rel_paths(bad)


def test_invalid_unc_rel_path_rejected():
    bad = _load(_detection_examples()[0])
    bad["input"]["rel_path"] = "\\\\server\\share\\img.fits"
    assert _check_rel_paths(bad)


def test_invalid_manifest_session_in_two_splits_rejected():
    data = _load(EXAMPLES_DIR / "corpus-manifest.json")
    data["splits"]["development"]["session_ids"].append("s003")
    _, errs = _manifest_index(data)
    assert any("split mismatch" in e or "not listed" in e for e in errs)
