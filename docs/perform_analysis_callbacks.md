# perform_analysis callbacks — developer guide

This note documents the expectations for the `perform_analysis()` function so Qt integration (Phase 2) and other callers can rely on a stable contract and developers can implement responsive analysis functions.

## Function signature

perform_analysis(input_dir, output_log, options, callbacks=None)

- input_dir: str — path of folder to analyze
- output_log: str — path to the log / output file
- options: dict — analysis options (SN R detection, trail detection flags, dirs for rejects, etc.)
- callbacks: dict | None — optional callbacks the analysis code SHOULD use to report progress/status/logs and to support cancellation.

## Required callbacks

If `callbacks` is provided, `perform_analysis()` SHOULD use the following keys when appropriate (these are provided by the Qt worker and tests):

- `status` (callable)
  - Example: callbacks['status']('status_key', text='Processing folder')
  - Purpose: short status tokens or messages to inform UI status bar or progress stage.

- `progress` (callable)
  - Example: callbacks['progress'](15.0)
  - Purpose: report numeric progress 0..100 (float). UI uses this to update progress bars.

- `log` (callable)
  - Example: callbacks['log']('Analyzing file: foo.fits')
  - Purpose: forward human-readable log lines to the UI log window and the persistent log file.

- `is_cancelled` (callable)
  - Example: if callbacks['is_cancelled'](): break
  - Purpose: allow long-running analysis to stop early when the user requests cancellation. The Qt worker exposes this helper for responsive cancellation.
  - Usage: `perform_analysis()` MUST check this periodically (e.g., between file loops, between heavy steps) and cleanly return if cancelled.

Notes:
- `is_cancelled` is deliberately lightweight (synchronous boolean check); it is the recommended cancellation mechanism for code paths that cannot be interrupted with low-level signals.
- Do NOT rely on `is_cancelled` being present; if `callbacks` is None or doesn't include this key, code should continue normally.

## Optional behavior and return value

- `perform_analysis()` may return a result object (typically a `list` of dicts representing analysis results). The worker will emit these via the `resultsReady` signal.
- In cancellation cases, it is OK for `perform_analysis()` to return partial results. The worker will emit `finished(True)` when cancellation was requested.

## Minimum compliance checklist for new implementations

- [ ] Accept `callbacks` kwarg and call `callbacks['log']`, `callbacks['progress']`, and `callbacks['status']` as appropriate.
- [ ] Periodically check `callbacks.get('is_cancelled', lambda: False)()` and return early if True.
- [ ] If returning results while cancelled, still ensure logs and progress are coherent before returning.

## Example usage pattern

```
for item in items:
    if callbacks and callbacks.get('is_cancelled') and callbacks['is_cancelled']():
        callbacks['log']('Cancellation detected — exiting early')
        return partial_results
    # process item
    callbacks['progress'](calc_progress)
    callbacks['log'](f'processed {item}')
```

## Rationale

Providing `is_cancelled` in callbacks keeps the cancellation contract straightforward and avoids heavy threading coupling between the worker and the analysis function. It keeps the analysis function testable (callbacks can be faked) and improves UX (UI stays responsive and can cancel long runs).
