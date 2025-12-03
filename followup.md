## `followup.md`

```markdown
# Follow-up checklist for ZeAnalyser Qt visualisation, i18n & skin

Use this file to drive **small, focused iterations**.  
Each pass should keep the app runnable and tests passing.

---

## Pass 1 – SNR histogram parity

- [x] Align SNR histogram data selection in Qt with Tk.
- [x] Add vertical dashed red lines for SNR min/max (from slider).
- [x] Hook slider change → update SNR range + vertical lines + label.
- [x] Add Matplotlib NavigationToolbar under the SNR figure.
- [x] Ensure cleanup() closes figures, canvases, and toolbars.

**When done:** Qt SNR tab “looks like” the Tk one and is fully interactive.

---

## Pass 2 – Other visualisation tabs

- [x] FWHM distribution:
  - [x] Implement RangeSlider + dashed lines, same behaviour as Tk.
  - [x] Store current min/max values on the Qt instance.
- [x] Eccentricity distribution:
  - [x] Match Tk histogram and labels.
- [x] Starcount distribution:
  - [x] Ensure histogram and slider behaviour match Tk (and extended Qt logic).
- [x] FWHM vs e:
  - [x] Implement scatter plot with same axes and titles as Tk.
- [x] SNR comparison:
  - [x] Implement “best vs worst N” bar charts as in Tk.

**When done:** All visualisation tabs present in Tk are present and functional in Qt.

---

## Pass 3 – Recommendations logic & application

- [x] Port `_compute_recommended_subset` logic from Tk to Qt:
  - [x] Same filtering criteria for the candidate images.
  - [x] Same percentile calculations.
  - [x] Same OK/KO conditions.
- [x] Wire the Qt sliders (SNR/FWHM/ecc/starcount) to recompute recommendations.
- [x] Update the summary text label with thresholds, following the Tk format.
- [x] Fill the QTreeWidget with recommended images and enable/disable the “Apply” button accordingly.
- [x] Implement `_apply_current_recommendations` using Tk behaviour as reference:
  - [x] Update `action` and `rejected_reason`.
  - [x] Refresh the main table.
  - [x] Log a clear message.
- [x] Fix the “No images are recommended for application” message:
  - [x] Only display it when there are truly zero recommended images.

**When done:** Recommendations in Qt produce the same subset and workflow as in Tk.

---

## Pass 4 – Settings tab: Language + Skin

- [x] Add the “Settings / Préférences” tab.
- [x] Inside, create two group boxes: Language & Skin.

### Language

- [x] Import `get_initial_language`, `set_language`, `lock_language` with safe fallbacks.
- [x] Remove old language selector from the Project tab.
- [x] Create `self.lang_combo` with values (System, fr, en, plus any extra languages from `zone.translations`).
- [x] Initialise selected language from:
  - [x] CLI option (if present), else
  - [x] QSettings `"language"`, else
  - [x] `get_initial_language()`.
- [x] Connect combo change:
  - [x] Call `set_language(lang)`.
  - [x] Save to QSettings.
  - [x] Call `_retranslate_ui()` to update texts.

### Skin

- [x] Add `self.skin_combo` with values (“System default”, “Dark”).
- [x] Implement `apply_skin()` to set Qt style and palette.
- [x] Read initial skin from QSettings `"skin"` and apply it at startup.
- [x] Connect combo change → `apply_skin()` + save to QSettings.

**When done:** The new Settings tab controls language and skin. Changes persist and take effect immediately.

---

## Pass 5 – Polish & tests

- [x] Audit `_retranslate_ui` and ensure every user-visible string comes from translations.
- [x] Remove any hard-coded French strings replaced by translation keys.
- [x] Run existing test suite and fix regressions.
- [x] Add minimal new tests (if possible) for:
  - [x] Construction of Settings tab (language/skin combos exist).
  - [x] `_compute_recommended_subset` behaviour with a small fake dataset.
  - [x] `_visualise_results` doesn’t crash when given a small list of rows.

**Final check:**  
Qt and Tk give the same visualisation & recommendation behaviour on the same log file, and the user can switch language and skin from the Settings tab without restarting the app.
