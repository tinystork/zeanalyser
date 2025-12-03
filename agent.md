# Mission: Qt Visualisation parity, working i18n, and Skin selector for **ZeAnalyser**

You are working on the **ZeAnalyser** project.
The Tk GUI (`analyse_gui.py`) is the mature reference.
The Qt GUI (`analyse_gui_qt.py`) is the new PySide6 port and must reach feature parity and add some small UX upgrades.

---

## 📂 Relevant files (do *not* random-edit others)

- `analyse_gui.py`  → **reference Tk GUI**, especially:
  - `AstroImageAnalyzerGUI.visualize_results`
  - SNR/FWHM/Ecc/Starcount distribution tabs
  - SNR/FWHM/ecc/starcount sliders & callbacks
  - Recommendations tab (`_compute_recommended_subset`, recommendations tree, buttons)
  - Language selection (`current_lang`, `change_language`, `lock_language`)
- `analyse_gui_qt.py` → **current Qt GUI**, must be fixed/extended
  - `ZeAnalyserMainWindow`
  - `_visualise_results` (Qt visualisation dialog)
  - `_compute_recommended_subset`, `_apply_current_recommendations`
  - `_retranslate_ui` and any language-related helpers
- `zone.py`
  - translation keys for both GUIs
  - fallback `_` implementation when `zeseestarstacker.i18n` is not available
- `analysis_model.py`, `snr_module.py`, `ecc_module.py`, `starcount_module.py`, `trail_module.py`, `stack_plan.py`
  - **read-only** unless strictly needed; they provide data for the GUI

---

## 🎯 High-level goals

- [ ] 1. **Qt visualisation dialog matches / extends Tk visualisation**
- [ ] 2. **Recommendations tab & “Apply recommendations” work correctly in Qt**
- [ ] 3. **Language switching is functional and consistent with Tk**
- [ ] 4. **New “Settings” area with Language + Skin (dark/system) controls**
- [ ] 5. **All changes are cross-platform (Win / Linux) and tested**

---

## 1. Qt visualisation parity with Tk

Use `AstroImageAnalyzerGUI.visualize_results` in `analyse_gui.py` as the **authoritative reference** for behaviour and layout.

### 1.1 SNR distribution tab

- [ ] Compare Tk implementation (SNR tab) with Qt implementation inside `_visualise_results`:
  - Same data source: only rows with `status == 'ok'` and finite `snr`.
  - Same number of bins (20) and same general visual style.
- [ ] Add **vertical dashed red lines** for the currently selected SNR range:
  - Lines use the min/max values from the SNR `RangeSlider` (as in Tk).
  - Lines must update when the slider moves (hook the Qt slider callback).
- [ ] Ensure the **SNR slider** at the bottom behaves like Tk’s:
  - Initial range = `[min(snr), max(snr)]`.
  - Callback updates internal `current_snr_min` / `current_snr_max` attributes.
  - Callback also updates the label that shows the range (e.g. `(21.5, 36.3)`).
- [ ] Add a **Matplotlib navigation toolbar** (pan/zoom/home/save) under the figure, equivalent to Tk:
  - Use `NavigationToolbar2QT` from `matplotlib.backends.backend_qt5agg` or Qt6 equivalent.
  - Store toolbar references in `dialog._toolbars` (similar to `_canvases` / `_figures`) and clean them in `cleanup()`.

### 1.2 Other distribution tabs

- FWHM distribution:
  - [ ] Same binning and labels as Tk (`visu_tab_fwhm_dist`, `fwhm_distribution_title`, `number_of_images`).
  - [ ] Add a FWHM `RangeSlider` + vertical dashed lines, same behaviour as Tk.
- Eccentricity distribution:
  - [ ] Same histogram and grid.
- Starcount distribution:
  - [ ] Mirror Tk “starcount” histogram & slider if present; keep Qt’s extended logic (percentile slider) but UI should still feel consistent.
- FWHM vs e scatter:
  - [ ] Same scatter plot and labels as Tk (`FWHM vs e`).

### 1.3 SNR comparison tab

- [ ] Implement the SNR “best vs worst” comparison tab in Qt, following Tk logic:
  - Use top N and bottom N images (up to 10, symmetrical).
  - Horizontal bar charts with filenames on the y-axis.
  - Titles use translated strings: `visu_snr_comp_best_title`, `visu_snr_comp_worst_title`.

### 1.4 Detailed data & detected trails tabs

- [ ] Ensure the “Detailed Data” tab in Qt shows the **same fields** as Tk (snr, fwhm, ecc, trails, starcount, action, reason, etc.).
- [ ] Match the “Detected Trails” tab:
  - List only images with `has_trails == True`.
  - Columns and labels consistent with Tk translations.

---

## 2. Recommendations tab & “Apply recommendations”

Qt already has a recommendations tab, but the behaviour must match the Tk GUI.

Use `_compute_recommended_subset` and related code in `analyse_gui.py` as the reference.

### 2.1 Recompute logic

- [ ] Ensure Qt `_compute_recommended_subset`:
  - Uses only images with:
    - `status == 'ok'`
    - `action == 'kept'`
    - `rejected_reason is None`
    - finite `snr` values
  - Computes percentiles based on:
    - `self.reco_snr_pct_min`
    - `self.reco_fwhm_pct_max`
    - `self.reco_ecc_pct_max`
    - `self.reco_starcount_pct_min` (only if `self.use_starcount_filter` is enabled)
  - Applies the same filter logic as Tk (`ok_snr`, `ok_fwhm`, `ok_ecc`, `ok_sc`).

### 2.2 UI updates and text

- [ ] In the Qt visualisation recommendations tab:
  - Re-use the same text template as Tk for the summary label:
    - `visu_recom_text_all`, plus the SNR/FWHM/ecc/starcount thresholds.
  - Tree widget columns:
    - Filename, SNR, FWHM, e, starcount (with same numeric formatting).
- [ ] Keep the different “Apply recommendations” buttons in sync:
  - Main window button (if present),
  - Visualisation dialog button,
  - Stack tab button.
- [ ] Fix the message **“No images are recommended for application”**:
  - Only show this message when `_compute_recommended_subset` returns an empty list.
  - If there are recommended images, ensure the “Apply recommendations” button is enabled and doesn’t show that message.

### 2.3 Apply recommendations to actions

- [ ] `_apply_current_recommendations` in Qt must:
  - Mark recommended rows with `action='kept'` and non-recommended ones with `action='rejected'` (or the same decision logic used in Tk).
  - Update `rejected_reason` fields consistently with Tk.
  - Refresh the main results view and any pending actions (SNR/FWHM/ecc/starcount/sat trails).
  - Log the operation to the GUI log area (and file if applicable).

---

## 3. Language switching (i18n) – Qt

Goal: Qt must use the **same i18n system** as Tk (when running inside ZeSeestarStacker) and still behave gracefully when `zeseestarstacker.i18n` is not available.

### 3.1 Imports and helpers

- [ ] At the top of `analyse_gui_qt.py`, add a robust i18n import:

```python
try:
    from zeseestarstacker.i18n import get_initial_language, set_language, lock_language
except ImportError:
    def get_initial_language():
        # Fallback to system language (fr/en) or just 'fr'
        return 'fr'
    def set_language(lang):
        pass
    def lock_language(value=True):
        return value
````

* [ ] Keep `import zone; _ = zone._` but **remove any calls to `zone.set_lang`** (they fail silently today).
* [ ] Make sure `_translate` (used for log-format strings) no longer hard-codes French:

  * Use the same current language as `get_initial_language()` / `set_language()`, or better, read from `zone.translations` using the active language.

### 3.2 New “Settings / Preferences” tab

* [ ] In `ZeAnalyserMainWindow._build_ui` (or equivalent), create a new top-level tab:

  * Name: `"Settings / Préférences"` (translated with `_('settings_tab_title')` if a key exists; otherwise a literal is OK).
* [ ] Inside this tab, create two **group boxes**:

  1. “Language / Langue”
  2. “Skin / Apparence”

### 3.3 Language group

* [ ] Remove the old language combo from the Project/Config area (if still present).
* [ ] Add:

  * A label: `_("lang_label")` if defined, else `"Language / Langue"`.
  * A `QComboBox` `self.lang_combo` with choices:

    * `System` (follow OS default)
    * `fr`
    * `en`
    * (extra languages may exist in `zone.translations`; populate dynamically from that dict when possible.)
* [ ] Initial selection rules:

  * If a language is forced on the CLI (existing `initial_lang` parameter), use that and disable the combo.
  * Else, read from QSettings (`"language"` key) if present.
  * Else, use `get_initial_language()` (which may already do system detection).
* [ ] When the user changes the combo:

  * Map the selection to a language code (e.g. `"fr"`, `"en"`, or `"system"`).
  * Call `set_language(lang_code)` (for `"system"`, pass the language detected by `get_initial_language()`).
  * Persist to `QSettings` under a `"language"` key.
  * Call `self._retranslate_ui()` to refresh all labels, tab titles, group boxes, and buttons.
  * Also refresh any cached texts in the visualisation dialog titles if needed.

### 3.4 `_retranslate_ui` completeness

* [ ] Ensure `_retranslate_ui` updates **all visible texts**:

  * Main tabs: Project, Results, Stack Plan, etc.
  * Group boxes and labels in the main window.
  * Buttons in the bottom toolbar.
  * The “Visualiser les résultats” window title and tab labels when the dialog is created.
* [ ] Cross-check against `self.widgets_refs` usage in `analyse_gui.py`:

  * Tk registers all widgets in `widgets_refs` and uses it for retranslation.
  * Mirror that mechanism or create a similar one for Qt (e.g. store references in dicts and loop over them).

---

## 4. Skin / theme selector (dark vs system)

Add a simple appearance selector in the same Settings tab.

### 4.1 UI

* [ ] In the “Skin / Apparence” group box:

  * Add a label and a `QComboBox` `self.skin_combo` with values:

    * `"System default"`
    * `"Dark"`
* [ ] Load the initial value from `QSettings` (`"skin"` key), defaulting to `"System default"`.

### 4.2 Theme application

* [ ] Implement `apply_skin(self, mode: str)` on `ZeAnalyserMainWindow`:

  * For `"System default"`:

    * Use the platform’s default style and palette:

      * `app.setPalette(app.style().standardPalette())`
  * For `"Dark"`:

    * Use the `Fusion` style and set a dark `QPalette`
      (standard Qt dark palette: dark window background, light text, etc.).
    * Apply to the global QApplication instance.

* [ ] Connect `self.skin_combo.currentTextChanged` to `apply_skin` and store the chosen mode in `QSettings`.

* [ ] Ensure the theme is applied as early as possible when the app starts:

  * Read `QSettings` before constructing the main window or at the very start of `ZeAnalyserMainWindow.__init__`.

---

## 5. Cross-platform and tests

* [ ] Avoid any platform-specific APIs; stick to PySide6, NumPy, Matplotlib.
* [ ] Keep all existing behaviour on Windows intact; don’t break CLI options.
* [ ] Add or update tests (if present) to cover:

  * Construction of the Settings tab and language/skin combos.
  * Basic callability of `_visualise_results` with a small fake dataset.
  * `_compute_recommended_subset` returns the same set as Tk for a given small in-memory dataset.

---

## ✅ Definition of Done

* [ ] SNR/FWHM/Ecc/Starcount visualisation tabs in Qt look and behave like the Tk ones (bins, sliders, dashed lines, nav toolbar).
* [ ] SNR comparison, detected trails, and detailed data tabs are present in Qt and show the same information as Tk.
* [ ] The Recommendations tab computes the same suggested subset as Tk, the tree is filled, and “Apply recommendations” actually updates actions and the main table. No more spurious “No images are recommended for application” messages when there *are* recommendations.
* [ ] Language selection in Qt is functional, persists between runs, and matches the i18n system used by Tk when available.
* [ ] A Settings tab lets the user pick both language and skin; the dark theme works and is persisted.
* [ ] All new code is reasonably commented and does not introduce regressions in the existing tests.

````

---

