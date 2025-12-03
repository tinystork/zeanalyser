## `followup.md`

```markdown
# Follow-up checklist for ZeAnalyser Qt visualisation, i18n & skin

Use this file to drive **small, focused iterations**.  
Each pass should keep the app runnable and tests passing.

---

## Pass 1 – SNR histogram parity

- [ ] Align SNR histogram data selection in Qt with Tk.
- [ ] Add vertical dashed red lines for SNR min/max (from slider).
- [ ] Hook slider change → update SNR range + vertical lines + label.
- [ ] Add Matplotlib NavigationToolbar under the SNR figure.
- [ ] Ensure cleanup() closes figures, canvases, and toolbars.

**When done:** Qt SNR tab “looks like” the Tk one and is fully interactive.

---

## Pass 2 – Other visualisation tabs

- [ ] FWHM distribution:
  - [ ] Implement RangeSlider + dashed lines, same behaviour as Tk.
  - [ ] Store current min/max values on the Qt instance.
- [ ] Eccentricity distribution:
  - [ ] Match Tk histogram and labels.
- [ ] Starcount distribution:
  - [ ] Ensure histogram and slider behaviour match Tk (and extended Qt logic).
- [ ] FWHM vs e:
  - [ ] Implement scatter plot with same axes and titles as Tk.
- [ ] SNR comparison:
  - [ ] Implement “best vs worst N” bar charts as in Tk.

**When done:** All visualisation tabs present in Tk are present and functional in Qt.

---

## Pass 3 – Recommendations logic & application

- [ ] Port `_compute_recommended_subset` logic from Tk to Qt:
  - [ ] Same filtering criteria for the candidate images.
  - [ ] Same percentile calculations.
  - [ ] Same OK/KO conditions.
- [ ] Wire the Qt sliders (SNR/FWHM/ecc/starcount) to recompute recommendations.
- [ ] Update the summary text label with thresholds, following the Tk format.
- [ ] Fill the QTreeWidget with recommended images and enable/disable the “Apply” button accordingly.
- [ ] Implement `_apply_current_recommendations` using Tk behaviour as reference:
  - [ ] Update `action` and `rejected_reason`.
  - [ ] Refresh the main table.
  - [ ] Log a clear message.
- [ ] Fix the “No images are recommended for application” message:
  - [ ] Only display it when there are truly zero recommended images.

**When done:** Recommendations in Qt produce the same subset and workflow as in Tk.

---

## Pass 4 – Settings tab: Language + Skin

- [ ] Add the “Settings / Préférences” tab.
- [ ] Inside, create two group boxes: Language & Skin.

### Language

- [ ] Import `get_initial_language`, `set_language`, `lock_language` with safe fallbacks.
- [ ] Remove old language selector from the Project tab.
- [ ] Create `self.lang_combo` with values (System, fr, en, plus any extra languages from `zone.translations`).
- [ ] Initialise selected language from:
  - [ ] CLI option (if present), else
  - [ ] QSettings `"language"`, else
  - [ ] `get_initial_language()`.
- [ ] Connect combo change:
  - [ ] Call `set_language(lang)`.
  - [ ] Save to QSettings.
  - [ ] Call `_retranslate_ui()` to update texts.

### Skin

- [ ] Add `self.skin_combo` with values (“System default”, “Dark”).
- [ ] Implement `apply_skin()` to set Qt style and palette.
- [ ] Read initial skin from QSettings `"skin"` and apply it at startup.
- [ ] Connect combo change → `apply_skin()` + save to QSettings.

**When done:** The new Settings tab controls language and skin. Changes persist and take effect immediately.

---

## Pass 5 – Polish & tests

- [ ] Audit `_retranslate_ui` and ensure every user-visible string comes from translations.
- [ ] Remove any hard-coded French strings replaced by translation keys.
- [ ] Run existing test suite and fix regressions.
- [ ] Add minimal new tests (if possible) for:
  - [ ] Construction of Settings tab (language/skin combos exist).
  - [ ] `_compute_recommended_subset` behaviour with a small fake dataset.
  - [ ] `_visualise_results` doesn’t crash when given a small list of rows.

**Final check:**  
Qt and Tk give the same visualisation & recommendation behaviour on the same log file, and the user can switch language and skin from the Settings tab without restarting the app.
