# ZeAnalyser Detection Result Contract v1

**Status:** Public contract — scientific detector interoperability
**Contract:** `zeanalyser.detection-result.v1`
**Schema:** [`docs/schemas/detection-result-v1.schema.json`](schemas/detection-result-v1.schema.json) (JSON Schema Draft 2020-12)
**Budget protocol:** [`docs/benchmark-protocol-v1.md`](benchmark-protocol-v1.md)
**Version:** 1.0.0
**Applies to:** future trail detector (TRAIL) and transparency/veil detector (CLOUD)
**Date:** 2026-10-01

This document defines a self-describing, versioned result record that every
ZeAnalyser scientific detector (trail, transparency) MUST emit so that UI,
logs, exports, and re-opening can consume it without knowing the chosen engine.
It is a **contract**, not an implementation: no engine is required or selected
here (Hough vs MRT is deliberately undecided).

## 1. Identity and versioning

Every result MUST carry:

- `schema_version`: `"1.0.0"` (this contract's data version).
- `contract`: `"zeanalyser.detection-result.v1"`.
- `result_id`: unique, stable, non-empty identifier for the record.
- `detector`: object with `family` (`trail` | `transparency`), `backend_id`
  (stable engine identifier, e.g. `acstools.satdet`, `zeanalyser.hough.v0`),
  and `backend_version` (both non-empty).

Versioning is independent from the ZeAnalyser product version (`3.5.0`).
A breaking change to states, units, or coordinate semantics requires a new
`schema_version` (and a new `$id`/URN).

## 2. Closed execution states

The single source of truth is `state`. There is **no boolean `detected`
field** in v1; a bare `False` MUST NOT be re-introduced or inferred as a
measured negative.

Exact, closed state names and their mandatory flags:

| state | analysis_completed | backend_available | domain_covered | error | reason |
|---|---|---|---|---|---|
| `measured_positive` | true | true | true | null | null |
| `measured_negative` | true | true | true | null | null |
| `indeterminate` | attempted (either) | any | any | null | non-null |
| `measurement_failure` | false | any | any | non-null | null |
| `skipped` | false | any | any | null | non-null |
| `unavailable` | false | **false** | any | policy | non-null |

- `indeterminate`: the detector was attempted but the outcome is inconclusive;
  `analysis_completed` reflects whether the run finished; `reason` is required.
- `measurement_failure`: the detector was attempted but failed; `error` is
  required and non-null.
- `skipped`: analysis intentionally not run (upstream filter/policy);
  `reason` required.
- `unavailable`: backend/precondition unavailable; `backend_available` MUST be
  false and `reason` (or an error) MUST be present.

`indeterminate`, `skipped`, `unavailable`, `measurement_failure` carry **no
probative `detected=false`**; consumers MUST NOT treat them as negatives.

### Legacy migration (fail-safe)

The legacy boolean `has_trails` (and similar booleans) MUST NOT be silently
re-interpreted. Migration rule:

- A legacy `False` maps to `indeterminate` (unknown) **unless** there is proof
  of a successful execution (backend ran, no error, domain covered), in which
  case it may map to `measured_negative`.
- A legacy `True` maps to `measured_positive` only when accompanied by proof
  of a completed, successful execution.

This is fail-safe by default: absence of execution proof degrades to
`indeterminate`, never to a probative negative.

## 3. Input identity (non-private)

`input` MUST identify the frame without exposing private data:

- `corpus_id`: stable corpus identifier (required, non-private, non-empty).
- `rel_path`: optional corpus-relative, pseudonymized path. Never mandatory,
  never absolute. The schema forbids POSIX absolute (`/…`), home (`~…`),
  Windows drive (`C:…`), and Windows UNC (`\\server\share…`) prefixes
  syntactically.
- `sha256`: optional content hash. When present it MUST be 64 hexadecimal
  characters. Documented as optional so an expensive per-run hash is not
  required.
- `image_prep`: describes the logical 2D scientific artifact (see §4).

Absolute filesystem paths are forbidden as a required field.

## 4. Common image preparation (documented, not imposed)

Both detectors consume a **logical 2D scientific plane**. This contract does
not force the same final preprocessing on the two detectors; it only requires
that whatever was done is *declared*.

Declared via `image_prep` (all fields below are REQUIRED unless stated):

- `logical_kind`: `scientific_2d` — the actual scientific input. The
  auto-stretched preview is never the scientific input.
- `color_mode`: `mono` | `rgb` | `cfa`.
  - `mono`: direct use; `bayer_pattern`, `cfa_strategy`, and
    `rgb_luminance_formula` are null (or absent) and MUST NOT be required.
  - `rgb`: `rgb_luminance_formula` REQUIRED and non-empty (e.g. Rec.709 luma);
    `bayer_pattern` and `cfa_strategy` null/absent.
  - `cfa`: `bayer_pattern` REQUIRED non-null (`RGGB`/`BGGR`/`GRBG`/`GBRG`) AND
    `cfa_strategy` REQUIRED, using the bounded vocabulary `demosaic`
    (full-colour demosaic), `bin2x2` (2×2 colour-pooled bin), or `superpixel`
    (2×2 → 4 planes).
- `shape`, `dtype`, `hdu` (when FITS).
- Policies (all REQUIRED, non-empty): `nan_inf_policy`, `saturation_policy`,
  `invalid_pixel_policy`, `background_policy`.

Invariants:

- Original frame is immutable; detectors work on the logical plane, never
  modify the original.
- For transparency, photometry MUST be preserved (no auto-stretch, no
  non-linear transform as scientific input).
- All transforms and coordinate mappings MUST be reversible/documented.

## 5. Coordinate transformation (explicitly versioned)

`coordinate_transform` maps analysis coordinates → native pixels, versioned
independently:

- `version`: `"1.0.0"`.
- `method`: `scale_offset` or `affine` (exactly one active).
- `scale`, `offset`, `matrix`: **all three are ALWAYS present** (active vector/matrix or explicitly `null`).
  - `scale_offset`: `scale` + `offset` REQUIRED, each a length-2 vector
    (native = analysis × scale + offset); `matrix` MUST be `null`.
  - `affine`: `matrix` REQUIRED, a 2×3 matrix `[[a,b,c],[d,e,f]]` mapping
    `[x,y,1] → [a·x+b·y+c, d·x+e·y+f]`; `scale` and `offset` MUST be `null`.
- `pixel_convention`: `center` or `corner`.
- `origin_preserved`: **REQUIRED** boolean — true when analysis coordinates map
  back to native pixels without cropping, flipping, or silent resampling.

The origin MUST be preserved unless explicitly documented otherwise.

## 6. Trail measurements

`measurements` for `family: trail`:

- `segment_count`: number of geometric segments (distinct from physical trails).
- `physical_trail_count`: physical trails after colinear grouping; `null` when
  grouping was not performed.
- `segments`: array of `{segment_id, endpoints (two [x,y] in analysis coords),
  width_px, length_px, object_class}`.
- `trail_groups`: optional colinear grouping.
- `object_class_summary`: `satellite` | `aircraft` | `unknown` | `null`.
  `unknown` is always acceptable; satellite vs aircraft is **not** required
  (out of initial scope).

State coherence:

- `measured_positive` requires at least one segment (`segment_count ≥ 1` and a
  non-empty `segments` array).
- `measured_negative` requires `segment_count == 0`, empty `segments`, and
  `physical_trail_count` of `0` (or `null` if grouping was not performed).

Cross-record invariants (checked by the documentary test; JSON Schema cannot
express length equality or cross-reference integrity):

- `segment_count == len(segments)`.
- `physical_trail_count`, when non-null on a positive, is ≥ 1.
- every `trail_group.segment_ids` entry references an existing `segment_id`,
  and no `segment_id` is duplicated.

## 7. Transparency measurements

`measurements` for `family: transparency`:

- `relative_transmission` (nullable, non-negative): photometric, **relative**
  transmission normalized to a documented reference.
- `transmission_error` (nullable, non-negative).
- `veil_state`: `clear` | `probable_veil` | `unattributed_degradation` |
  `indeterminate`.
- `usable_for_stacking` (nullable): veil presence is **distinct** from
  stacking usefulness.
- `reference` (nullable object): documented origin and quality of the relative
  reference (method, reference session, frame count). **Required as a non-null
  object when `relative_transmission` is non-null** (a null reference with a
  numeric transmission is rejected by schema and test).
- `star_count_used` (nullable, non-negative integer).
- `star_fraction_recovered` (nullable, in `[0, 1]`).

State coherence:

- `measured_positive` (veil/degradation observed) requires `veil_state` in
  `probable_veil` | `unattributed_degradation`.
- `measured_negative` (clear measured) requires `veil_state == "clear"`.

Rules:

- There is **no `cloud_percent`** in v1. A cloud fraction requires a
  definition and calibration that does not exist yet; any future `cloud_percent`
  must carry its own definition/calibration and a new schema version.
- `veil_state` is an observational statement, not a weather attribution.
  `probable_veil` is NOT a certification of "cloud". A transmission drop does
  not prove a meteorological cause; dark clouds, the Moon, light pollution,
  nebulae, dew, and extinction are documented confounds (see the corpus contract).

## 8. Bounded reason/error

- `error` / `reason` are either `null` or `{code, message}`.
- `code` is a short machine-readable non-empty string (≤64 chars),
  `message` non-empty and ≤500 chars.
- Suggested `reason`/`error` codes: `low_star_density`,
  `reference_batch_inadequate`, `domain_not_covered`, `policy_skip`,
  `ambiguous`, `backend_unavailable`.

## 9. Provenance

`provenance` MUST carry `software {name, version}` (both non-empty),
`parameters_effective` (the parameters actually used, with explicit units),
and an ISO-8601 UTC `timestamp` (`format: date-time`).

## 10. Budgets and promotion gates

See [`docs/benchmark-protocol-v1.md`](benchmark-protocol-v1.md). No detector
is promoted without a quantified benchmark report attached to the documented
2MP Seestar-like reference profile. Trail recall ≥95% / FP ≤1% thresholds are
**PROPOSED, TO CONFIRM** — not achieved, not claimed.

## 11. Examples

- [`docs/examples/trail-measured-positive.json`](examples/trail-measured-positive.json) (affine transform)
- [`docs/examples/trail-measured-negative.json`](examples/trail-measured-negative.json)
- [`docs/examples/transparency-indeterminate.json`](examples/transparency-indeterminate.json)
- [`docs/examples/transparency-measurement-failure.json`](examples/transparency-measurement-failure.json)
- [`docs/examples/transparency-measured-negative.json`](examples/transparency-measured-negative.json)

The examples contain no personal data, absolute paths, or secrets, and cover
both `scale_offset` and `affine` coordinate transforms.
