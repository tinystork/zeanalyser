# ZeAnalyser Process Contract (Interoperability)

**Status:** Public contract — ZeSoftware interoperability
**Version:** 1
**Applies to:** ZeAnalyser product (entry point `zeanalyser`), ZeSeestarStacker consumer
**Date:** 2026-08-19

This document formalises the process-level contract that ZeAnalyser exposes
to other ZeSoftware products (currently consumed by ZeSeestarStacker to
launch folder analysis and retrieve the recommended reference frame).
It follows the ZeSoftware Interoperability Rules (rules 2, 19, 21, 22):
discovery by metadata/entry point, documented process protocol, graceful
degradation when absent.

## 1. Discovery

A consumer MUST discover ZeAnalyser through stable mechanisms, in this order:

1. the `zeanalyser` console/GUI entry point on `PATH`
   (`gui_scripts: zeanalyser = zeanalyser.analyse_gui_qt:main`);
2. the Python module form `python -m zeanalyser` (when the distribution is
   installed in the same interpreter);
3. otherwise the product is considered **absent** and the consumer MUST
   degrade gracefully (disable the integration, keep the rest of the
   application functional).

Discovery MUST NOT rely on repository adjacency, checkout layout, or
inspection of another project's source tree.

## 2. Launch protocol

The consumer launches ZeAnalyser as a separate non-blocking subprocess:

```text
zeanalyser --input-dir <DIR> --lang <en|fr> --lock-lang
```

- `--input-dir` : folder to analyse (pre-filled in the UI).
- `--lang` : initial UI language (`en` or `fr`).
- `--lock-lang` : lock the language selector (prevents the user from
  switching language in the launched window).

The subprocess is the UI itself: it stays open until the user closes it.
The consumer MUST NOT block its own UI while ZeAnalyser runs.

## 3. Reference return protocol (command file)

To receive the recommended reference frame without modifying ZeAnalyser's
CLI, the consumer:

1. creates a unique temporary file (e.g. `analyzer_stack_command_<pid>.txt`
   under the system temp directory);
2. exports the environment variable `ZEANALYSER_COMMAND_FILE=<path>` for the
   ZeAnalyser subprocess;
3. watches the file (polling) while ZeAnalyser runs;
4. when the user requests "send reference to main" in ZeAnalyser, ZeAnalyser
   writes the file and the consumer reacts.

### File format (protocol v1)

Text file, UTF-8, one `KEY=VALUE` pair per line:

```text
REFERENCE=<absolute path to the best reference FITS file>
TIMESTAMP=<YYYY-MM-DD HH:MM:SS>
```

- `REFERENCE` : the recommended reference frame (absolute path).
- `TIMESTAMP` : local time of the write (informational).
- Unknown lines MUST be ignored by consumers.
- ZeAnalyser updates the file in place (removes stale `REFERENCE=` /
  `TIMESTAMP=` lines, appends the new ones). Consumers MUST treat the file
  as a snapshot: read all lines, parse `REFERENCE=`, then delete the file.
- Consumers MUST delete the file after a successful read (best-effort: a
  deletion failure does not invalidate the already-read reference).

### Consumer behaviour on absence of REFERENCE

If the file exists but contains no `REFERENCE=` line (or the file never
appears), the consumer MUST NOT start processing and SHOULD continue
watching until ZeAnalyser exits or a timeout is reached.

## 4. Graceful degradation

- ZeAnalyser absent / not importable → the consumer MUST disable only the
  ZeAnalyser-dependent feature (folder analysis) with a clear user message;
  the rest of the consumer application MUST remain fully functional.
- ZeAnalyser present but incompatible (older CLI without the expected
  flags) → the consumer SHOULD detect the failure at launch and fall back
  to the same "feature unavailable" state.

## 5. Versioning

This contract is versioned independently from the ZeAnalyser product
version.  Protocol v1 is implemented by ZeAnalyser >= 3.3 and consumed by
ZeSeestarStacker >= 7.0.2.  A breaking change to the file format or launch
flags requires a new protocol version and a consumer-side compatibility
check (per ZeSoftware Interoperability Rules, rule 3).

## 6. Contract lock (tests)

The ZeAnalyser test suite contains `tests/test_process_contract.py`, which
verifies that the source still implements the identifiers of this contract
(`ZEANALYSER_COMMAND_FILE`, `REFERENCE=`, `TIMESTAMP=`).  Any accidental
renaming of these identifiers fails the lock and requires an explicit
protocol version bump.
