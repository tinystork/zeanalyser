# Mission: Restore acstools availability indicator in Qt "Trail Detection" section

## Goal
In `analyse_gui_qt.py`, the "Trail Detection" UI is missing the small status indicator present in the Tkinter GUI:
- show an inline text indicator next to the trail detection checkbox
- green when acstools is usable, red when missing/incompatible
- translated using existing zone keys

This must match the Tk behavior conceptually (based on SATDET flags from `trail_module.py`).

## Scope (STRICT)
- Modify **only**: `analyse_gui_qt.py`
- Do NOT touch: `analyse_gui.py`, `trail_module.py`, other modules.
- Do NOT change any analysis logic, only UI.

## Requirements
- [x] Add a QLabel next to the checkbox `self.detect_trails_cb` inside the Trail Detection group.
  - Layout: checkbox + a small status label on the same row (like Tk).
  - The label text must be wrapped in parentheses: `( . )`.
- [x] Status rules (use `trail_module` flags):
  - Read `SATDET_AVAILABLE` and `SATDET_USES_SEARCHPATTERN` from `trail_module` (safe import).
  - If `SATDET_AVAILABLE` is False => text key `acstools_missing`, color **red**
  - Else if `SATDET_USES_SEARCHPATTERN` is False => text key `acstools_sig_error`, color **orange** (optional but recommended; matches existing keys)
  - Else => text key `acstools_ok`, color **green**
- [x] Translation:
  - Use existing translation mechanism already used in `analyse_gui_qt.py` (same `_()` / `_tr()` pattern).
  - Ensure label updates when language changes:
    - update it from the UI retranslate function (whatever the file uses for retranslation).
- [x] Robustness / no crash:
  - `analyse_gui_qt.py` supports headless / missing-Qt environments by setting Qt classes to `object`.
  - Your changes MUST respect that:
    - if `QLabel is object` or checkbox not created, skip silently.
    - wrap updates in try/except; never raise.

## Implementation outline
- [x] Add an attribute: `self.acstools_status_label = QLabel("")` (guarded).
- [x] Create a helper method (or small inline function) `_update_acstools_status_label()` that:
  - imports `trail_module` safely
  - decides text + color
  - applies `setText(f"({text})")`
  - applies `setStyleSheet("color: ...;")` (simple is fine)
- [x] Call `_update_acstools_status_label()`:
  - after creating the Trail Detection widgets (end of that group build)
  - inside the retranslate routine after setting texts

## Acceptance criteria
- [ ] With acstools usable: label visible and green.
- [ ] Without acstools / incompatible: label visible and red.
- [ ] Language switch updates the label text immediately.
- [ ] No other UI regression in Trail Detection.
- [ ] No crash when PySide6 is missing.
