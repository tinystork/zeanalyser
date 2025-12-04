# Mission: Fix Qt progress callback crash when value is "indeterminate" (ZeAnalyser V3 / analyse_gui_qt.py)

## Context

On Linux, a user gets this error in the Qt GUI during analysis:

- `ERROR: could not convert string to float: 'indeterminate'`
- Then: `Worker finished: cancelled=True`

The analysis itself has already run fine; the crash comes from the **Qt progress callbacks** trying to cast a non-numeric value to `float`.

The existing analysis core (shared with the Tk GUI) sometimes calls the `progress_callback` with special values like:

- `"indeterminate"` or
- `None`

to indicate “indeterminate progress bar” rather than a numeric percentage.

Tk handles this gracefully and just switches the progress bar mode:

```python
elif value is None or value == 'indeterminate':
    self.progress_bar.config(mode='indeterminate')
````

But the Qt side currently does:

```python
'progress': lambda v: self.progressChanged.emit(float(v)),
```

both in:

* `AnalysisWorker._run_analysis_callable(...)` and
* `AnalysisRunnable.run(...)`

This leads to `ValueError: could not convert string to float: 'indeterminate'` when the analysis core sends that value.

Your mission is to make these progress callbacks robust so they **ignore non-numeric values** (especially `"indeterminate"` and `None`) instead of crashing, while keeping the rest of the code intact.

---

## Files to edit

* `analyse_gui_qt.py`

  * class `AnalysisWorker`

    * method `_run_analysis_callable`
  * class `AnalysisRunnable`

    * method `run`

⚠️ Do **not** change the analysis core modules (`analyse_logic.py`, etc.). The fix must be entirely in the Qt worker layer.

---

## Tasks

### 1. Harden `AnalysisWorker._run_analysis_callable` progress callback

1. Open `analyse_gui_qt.py` and locate:

   ```python
   def _run_analysis_callable(self, analysis_callable, *args, **kwargs):
       ...
       callbacks = {
           'status': lambda key, **kw: self.statusChanged.emit(str(key)),
           'progress': lambda v: self.progressChanged.emit(float(v)),
           'log': log_cb,
           'is_cancelled': lambda: bool(self._cancelled),
       }
   ```

2. Replace the inline `lambda` for `progress` with a small helper function that:

   * Accepts `v`
   * If `v` is `None` or the string `"indeterminate"`, **returns early** (no emit, no crash).
   * Otherwise tries to convert to `float` and emit.
   * Catches any other exception and silently ignores it (to avoid killing the worker for a cosmetic issue).

   Example target behaviour:

   ```python
   def progress_cb(v):
       try:
           if v is None or v == 'indeterminate':
               # Special "indeterminate" mode from the core: this should NOT
               # crash the worker. We just skip updating the numeric bar.
               return
           self.progressChanged.emit(float(v))
       except Exception:
           # Never let a bad progress value kill the worker thread.
           pass

   callbacks = {
       'status': lambda key, **kw: self.statusChanged.emit(str(key)),
       'progress': progress_cb,
       'log': log_cb,
       'is_cancelled': lambda: bool(self._cancelled),
   }
   ```

3. Keep the rest of `_run_analysis_callable` unchanged (including the final `self.progressChanged.emit(100.0)` and the `resultsReady` logic).

---

### 2. Harden `AnalysisRunnable.run` progress callback in the same way

1. In the same file, find class `AnalysisRunnable` and its `run` method:

   ```python
   class AnalysisRunnable(QRunnable):
       ...
       def run(self):
           # Run the callable and forward logs/progress via signals
           try:
               callbacks = {
                   'status': lambda key, **kw: self.signals.statusChanged.emit(str(key)),
                   'progress': lambda v: self.signals.progressChanged.emit(float(v)),
                   'log': lambda key, **kw: self.signals.logLine.emit(
                       str(key) if isinstance(key, str) else str(kw)
                   ),
               }
               ...
   ```

2. As above, replace the inline lambda by a helper function with the same semantics:

   ```python
   def _emit_progress(self, v):
       """Convert v to float if possible; ignore 'indeterminate'/None/etc."""
       try:
           if v is None or v == 'indeterminate':
               return
           self.signals.progressChanged.emit(float(v))
       except Exception:
           # Never make the runnable crash on progress conversion issues
           pass

   def run(self):
       try:
           callbacks = {
               'status': lambda key, **kw: self.signals.statusChanged.emit(str(key)),
               'progress': self._emit_progress,
               'log': lambda key, **kw: self.signals.logLine.emit(
                   str(key) if isinstance(key, str) else str(kw)
               ),
           }
           ...
   ```

3. Do not change the rest of `run` (including `self.signals.progressChanged.emit(100.0)` at the end).

---

### 3. Ensure signals’ types stay compatible

* `progressChanged` is currently declared as `Signal(float)` in both `AnalysisWorker` and `AnalysisRunnable.WorkerSignals`.
* Even though we sometimes **don’t** emit when value is `"indeterminate"`, whenever we *do* emit, it must still be with a `float`.
* Do **not** change the signal signatures; only change how we call them.

---

### 4. Add a small internal test helper (optional but nice)

To guard against regressions, you can add a tiny internal test function (kept in `analyse_gui_qt.py` under `if __name__ == "__main__":` or protected by a `DEBUG` flag) that:

* Creates an `AnalysisWorker`

* Defines a fake `analysis_callable` which calls:

  ```python
  callbacks['progress']('indeterminate')
  callbacks['progress'](None)
  callbacks
  ```

* Verifies that:

  * No exception is thrown
  * `progressChanged` is ultimately emitted with a float (e.g. 42.0 and/or 100.0).

This is optional; focus first on fixing the actual bug.

---

## Acceptance criteria

* [ ] Running `analyse_gui_qt.py` on Linux with a real dataset no longer triggers:
  `could not convert string to float: 'indeterminate'`.
* [ ] The worker **does not** finish as `cancelled=True` just because of progress issues.
* [ ] Logs still show normal analysis activity, and the final log line includes:
  `"Worker finished, QThread stopped."` without an error right before.
* [ ] The progress bar still updates numerically when the core sends numeric values.
* [ ] Tk GUI behaviour is unchanged.

---

## Nice-to-have sanity checks

* [ ] Run a quick analysis on Windows with the Qt GUI and confirm that progress and logs behave as before.
* [ ] Run on Linux with the same dataset that previously crashed and confirm smooth completion.
* [ ] Grep the repo for other `progressChanged.emit(float(` and ensure there’s no other fragile case that could see `"indeterminate"` (if any exist, harden them the same way).

