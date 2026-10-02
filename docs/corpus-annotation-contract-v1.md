# ZeAnalyser Corpus Annotation Contract v1

**Status:** Public contract — corpus and annotation format
**Contract:** `zeanalyser.corpus-manifest.v1`
**Schema:** [`docs/schemas/corpus-manifest-v1.schema.json`](schemas/corpus-manifest-v1.schema.json) (JSON Schema Draft 2020-12)
**Version:** 1.0.0
**Applies to:** shared annotated corpus for TRAIL and CLOUD detectors
**Date:** 2026-10-01

This document defines the manifest and annotation format for a shared,
leak-free corpus used to tune and validate the trail and transparency/veil
detectors. It is a **format and rules document**, not a delivered corpus:
no real corpus is shipped and no user image is copied into the repository.

## 1. Manifest identity

A manifest MUST carry `schema_version: "1.0.0"`, `contract:
"zeanalyser.corpus-manifest.v1"`, a non-empty `manifest_id`, and a `corpus`
block with `phase` (`initial` | `extended`) and a `target_image_count`
**objective** range (`min` ≤ `max`, enforced by the cross-record test).

## 2. Grouping and splits (anti-leak)

Images are grouped by `session_id` and `target_id`. The fundamental anti-leak
rule: **a session or target belongs to exactly one split, as a whole group.**
Related images MUST NOT be distributed across `development` and `validation`.

Splits are closed:

- `development` — tuning.
- `validation` — held-out validation.
- `holdout` — optional final holdout.

No random per-file splitting. A split is declared by listing whole
`session_ids` / `target_ids`. The cross-record test enforces that every split
list matches the session/target assignments exactly (no duplication, no
orphan, one split per group).

### Anti-leak rules (normative)

The following MUST stay in the same split as their siblings:

1. neighboring poses (temporally or spatially adjacent frames of a session);
2. dithers of the same field;
3. copies/exports/derivatives of the same original frame;
4. series (time-lapse) of the same target;
5. mosaics / overlapping panels of the same field.

Rationale: a detector tuned on frame N must never be tested on frame N±1 of
the same sequence, because they are near-duplicates and would leak.

## 3. Phase and size

- Initial phase objective: **100–200 images** (this is an objective, not a
  delivered count).
- Extended phase: add negatives to measure rare false positives, keeping the
  held-out set untouched.

## 4. Annotation entries

Annotations are **separate per kind** (`trail`, `transparency`) and MUST NOT
be merged into one label. Each entry:

- `annotation_id`, `image_id` (references a `session.image_ids` entry), both
  non-empty.
- `kind`: `trail` | `transparency`.
- `label`: `present` | `absent` | `uncertain` | `not_applicable`.
- `confidence` (0..1, nullable).
- `annotator` (non-empty), `provenance` (tool, date, review status).
- `geometry` (nullable; trail segments when available).
- `object_class` (`satellite` | `aircraft` | `unknown` | `null`) — satellite
  vs aircraft distinction, unknown allowed.
- `stacking_usability` (`usable` | `unusable` | `uncertain` | `null`) — veil
  presence (`label`) is **distinct** from stacking usefulness.
- `reviewed` (**REQUIRED** boolean) — true when a second annotator reviewed it.

IDs MUST be unique across the manifest (sessions, targets, images,
annotations); the cross-record test enforces uniqueness and rejects orphaned
annotations and split lists that do not match the declared groups.

## 5. Review and disagreement policy

- `development` may be single-annotated (`reviewed` may be false).
- `validation` and `holdout` annotations MUST be reviewed by a **second
  annotator** (`reviewed: true`). The cross-record test enforces this on every
  validation/holdout image annotation.
- On disagreement, the record MUST be marked `uncertain` (or
  `not_applicable`), never silently resolved to one annotator's label.
- Disagreements and `uncertain` cases MUST be retained in the corpus (do not
  discard them), so detectors learn to abstain rather than guess.

## 6. Required case coverage

The corpus MUST eventually cover, across splits, at least:

- CFA / RGB / mono inputs; multiple camera models, resolutions, configurations.
- Dense and sparse star fields.
- Nebulae.
- Moon-adjacent / light-pollution frames.
- Poor MAP / tracking defects.
- Dew/condensation when known.
- Trails: axial, partial, faint, multiple; and "false friends" (aligned stars,
  filaments, defective columns, aircraft).
- Clear, uniformly veiled, partially veiled, and fully veiled batches.

CFA image references MUST carry a non-null `bayer_pattern`.

## 7. Privacy and storage

- **No user image is copied into the repository.**
- Only `rel_path` (corpus-relative, pseudonymized) is stored; never absolute
  paths, never real user paths. The schema forbids POSIX absolute (`/…`),
  home (`~…`), Windows drive (`C:…`), and Windows UNC (`\\server\share…`)
  prefixes syntactically.
- `sha256` is optional and, when present, MUST be 64 hex characters (no
  expensive per-run hash is required).

## 8. Confounds for transparency

Presence of veil must not be conflated with weather cause. Documented
confounds: dark clouds, Moon, light pollution, nebulae, dew, and extinction.
A transmission drop does not prove a meteorological cause; `cloud_percent`
without a definition/calibration is not part of v1.

## 9. Example

- [`docs/examples/corpus-manifest.json`](examples/corpus-manifest.json)

The example demonstrates sessions/targets/splits and multi-kind (trail +
transparency) annotations, obeys the anti-leak rule (each session/target
appears in exactly one split), and shows the double-review policy
(`validation`/`holdout` annotations have `reviewed: true`).
