# Follow-up checklist (Qt acstools status label)

## What to verify in code
- [x] `analyse_gui_qt.py`:
  - [x] the Trail Detection checkbox row now includes the new QLabel
  - [x] `self.acstools_status_label` (or similarly named attribute) exists
  - [x] `_update_acstools_status_label()` (or equivalent) is called:
    - [x] after building the trail section
    - [x] during UI retranslation (language change)
  - [x] all access guarded for headless mode (`QLabel is object`, try/except)

## Manual tests
- [ ] Normal run (acstools installed + compatible)
  - status shows "(...)" in green
  - checkbox remains usable
- [ ] Missing / incompatible acstools
  - status shows "(...)" in red
  - GUI does not crash
- [ ] Signature mismatch case (optional)
  - status shows "(...)" in orange (sig_error) if implemented
- [ ] Language switch
  - status label text updates immediately (no restart)

## Non-regression checks
- [x] No change to analysis outputs / options building.
- [x] No change to existing enable/disable logic for trail params.
- [x] No changes outside `analyse_gui_qt.py`.
