# Follow-up: Qt progress callback crash (“indeterminate”) – verification checklist

Use this checklist after applying the changes described in `agent.md`.

## 1. Code review

- [x] Confirm that in `AnalysisWorker._run_analysis_callable` (in `analyse_gui_qt.py`), the `callbacks['progress']` entry now uses a `progress_cb` helper that:
  - [x] Returns early when `v is None` or `v == 'indeterminate'`.
  - [x] Emits `progressChanged(float(v))` for numeric values.
  - [x] Catches and ignores any unexpected exceptions from float conversion.
- [x] Confirm that in `AnalysisRunnable.run`, the `callbacks['progress']` entry now uses a method like `self._emit_progress` with the same behaviour.
- [x] Verify that both `progressChanged` signals are still declared as `Signal(float)` and that every actual emit still uses a float.

## 2. Manual test – synthetic callable

- [ ] Temporarily add (or run from a REPL) a simple `analysis_callable` that:
  - [ ] Calls the provided `callbacks['progress']('indeterminate')`.
  - [ ] Calls `callbacks['progress'](None)`.
  - `.
- [ ] Run this callable via `AnalysisWorker.start(...)` or `AnalysisRunnable` and ensure:
  - [ ] No exception is raised.
  - [ ] The app does **not** log any `ValueError: could not convert string to float`.
  - [ ] `progressChanged` gets at least one numeric value (e.g. 42.0 or 100.0).

## 3. Manual test – real analysis (Linux)

- [ ] On Linux, launch the Qt GUI: `python3 analyse_gui_qt.py`.
- [ ] Select an input directory that previously triggered the bug.
- [ ] Run the analysis.
- [ ] Confirm in the log pane:
  - [ ] There is no `ERROR: could not convert string to float: 'indeterminate'`.
  - [ ] The worker ends with `"Worker finished, QThread stopped."`.
  - [ ] `cancelled=True` is **not** logged unless the user explicitly pressed “Cancel”.
- [ ] Confirm that the SNR logs (e.g. “SNR Marqué pour rejet … (SNR: 12.79 < 13.05)”) still appear as before.

## 4. Regression check – other platforms

- [ ] On Windows, run the same analysis via Qt GUI and confirm:
  - [ ] Progress bar behaves as before; no new errors show up.
  - [ ] Analysis finishes normally and results are still usable.
- [ ] If possible, ask at least one Linux tester to confirm the bug is gone with their dataset.

## 5. Cleanup & commit

- [x] Remove any temporary debug prints or test hooks that are not meant for production.
- [x] Run a quick `python -m py_compile` on the modified file(s) to ensure no syntax error slipped in.
- [x] Commit with a message like:

  > `Fix Qt progress callback for 'indeterminate' values (no more float conversion crash)`

- [ ] Push to the appropriate branch and let the maintainer know that Linux Qt users should `git pull` to get the fix.

If any tester still reports `could not convert string to float: 'indeterminate'` after these changes, re-check that **all** progress callbacks in `analyse_gui_qt.py` have been hardened and that the new code is indeed deployed (no stale .pyc, correct branch, etc.).
