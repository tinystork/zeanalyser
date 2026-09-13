"""i18n regression tests for mission ZA-I18N-GUI-LOG-ERRMSG-P0.6.

Covers:

* G1 - the dedicated GUI ``self._log`` translation keys resolve to real, formatted
       strings in both FR and EN (no ``_key_`` / raw-key leakage).
* G2 - source guard: migrated English literals no longer exist in
       ``analyse_gui_qt.py``.
* G3 - source guard: the normalized French error strings no longer exist in
       ``analyse_logic.py``.
* G4 - FR/EN key-set parity still holds and all newly added keys are present in
       both dictionaries.
"""

import string
from pathlib import Path

import pytest

import zeanalyser.analyse_gui_qt as mod
from zeanalyser.zone import translations

_QT_MISSING = mod.QApplication is object
needs_qt = pytest.mark.skipif(
    _QT_MISSING, reason="PySide6 not installed in this environment"
)

ROOT = Path(__file__).resolve().parents[1]
GUI_SOURCE = ROOT / "src" / "zeanalyser" / "analyse_gui_qt.py"
LOGIC_SOURCE = ROOT / "src" / "zeanalyser" / "analyse_logic.py"

# Every dedicated key added by this mission (must exist in FR and EN).
NEW_KEYS = [
    "gui_no_recommended_images_to_apply",
    "gui_stack_plan_autoload_failed",
    "gui_missing_output_path",
    "gui_using_input_dir_and_log",
    "gui_trail_reject_dir_required",
    "gui_snr_reject_dir_required",
    "gui_no_results_stack_plan",
    "gui_no_images_kept_for_stacking",
    "gui_stack_plan_created_with_batches",
    "gui_stack_plan_no_results",
    "gui_stack_plan_create_error",
    "gui_stacking_script_prepared_preview",
    "gui_no_stacking_script_generated",
    "gui_stacking_script_prepare_error",
    "gui_no_log_file_selected",
    "gui_log_file_not_found",
    "gui_open_log_failed",
    "gui_stack_plan_window_open_error",
    "gui_stack_plan_export_failed",
    "gui_stacking_script_write_failed",
    "gui_stacking_script_prepare_failed",
    "gui_apply_snr_filter_not_implemented",
    "gui_apply_fwhm_filter_not_implemented",
    "gui_visualization_json_decode_error",
    "gui_visualization_data_load_error",
    "gui_marker_manage_error",
    "gui_no_results_to_visualise",
    "gui_results_visualise_error",
    "gui_apply_reco_no_results",
    "gui_apply_reco_no_paths",
    "gui_apply_reco_error",
    "gui_apply_reco_inner_error",
    "gui_marked_good_images",
    "gui_unmarked_images",
    "gui_organizer_no_plan",
    "gui_organizer_error",
    "gui_auto_organize_error",
    "gui_apply_actions_error",
]

# Representative sample resolved at runtime (key -> kwargs).
RESOLVE_SAMPLE = [
    ("gui_no_results_stack_plan", {}),
    ("gui_no_log_file_selected", {}),
    ("gui_stack_plan_created_with_batches", {"path": "/tmp/plan.csv", "count": 3}),
    ("gui_visualization_json_decode_error", {"path": "/tmp/log.txt", "e": "boom"}),
    ("gui_visualization_data_load_error", {"path": "/tmp/log.txt", "e": "boom"}),
    ("gui_marker_manage_error", {"e": "boom"}),
    ("gui_apply_reco_no_results", {}),
    ("gui_using_input_dir_and_log", {"input": "/in", "log": "/out.log"}),
    ("gui_apply_actions_error", {"action_type": "SNR", "e": "boom"}),
    ("gui_marked_good_images", {"count": 4}),
]


@pytest.fixture
def lang_restore():
    """Unlock the language, yield the module, then restore the prior state."""

    saved_locked = mod._LANGUAGE_LOCKED
    saved_active = mod._ACTIVE_LANGUAGE
    mod._LANGUAGE_LOCKED = False
    try:
        yield mod
    finally:
        mod._LANGUAGE_LOCKED = False
        try:
            mod.set_language(saved_active)
        finally:
            mod._LANGUAGE_LOCKED = saved_locked


def _placeholders(text):
    names = set()
    for _literal, field_name, _spec, _conv in string.Formatter().parse(text):
        if field_name:
            names.add(field_name)
    return names


# --------------------------------------------------------------------------- G1
@needs_qt
@pytest.mark.parametrize("key,kwargs", RESOLVE_SAMPLE)
def test_new_gui_keys_resolve_in_both_languages(lang_restore, key, kwargs):
    mod = lang_restore
    for lang in ("fr", "en"):
        mod.set_language(lang)
        resolved = mod._(key, **kwargs)
        assert resolved, (lang, key)
        assert not resolved.startswith("_") and not resolved.endswith("_"), (
            lang,
            key,
            resolved,
        )
        assert key not in resolved, (lang, key, resolved)
        assert "{" not in resolved and "}" not in resolved, (lang, key, resolved)


@needs_qt
def test_new_gui_keys_fr_differs_from_en_for_error_messages(lang_restore):
    """Spot-check that the FR/EN pairs are genuinely localized, not copies."""

    mod = lang_restore
    mod.set_language("fr")
    fr = mod._("gui_visualization_json_decode_error", path="/tmp/log.txt", e="boom")
    assert fr == "ERREUR: Échec du décodage JSON depuis /tmp/log.txt: boom"
    mod.set_language("en")
    en = mod._("gui_visualization_json_decode_error", path="/tmp/log.txt", e="boom")
    assert en == "ERROR: failed to decode JSON from /tmp/log.txt: boom"


# --------------------------------------------------------------------------- G2
def test_migrated_gui_literals_are_gone_from_source():
    body = GUI_SOURCE.read_text(encoding="utf-8")
    old_literals = [
        'self._log("No results available for stack plan")',
        'self._log("No log file selected to open")',
        'self._log("No images kept for stacking")',
        'self._log("No stacking script generated")',
        'self._log("No results available to apply recommendations")',
        'self._log("Organizer: no plan to apply. Run a scan first.")',
        'self._log(f"ERREUR: Échec du décodage JSON',
        'self._log(f"Error managing markers: {e}")',
        'self._log(f"Stack plan created:',
    ]
    offenders = [lit for lit in old_literals if lit in body]
    assert not offenders, f"Un-migrated GUI literals remain: {offenders}"


# --------------------------------------------------------------------------- G3
def test_french_error_strings_are_gone_from_logic_source():
    body = LOGIC_SOURCE.read_text(encoding="utf-8")
    markers = (
        "Pas de données image valides",
        "Erreur analyse SNR/FITS",
        "Erreur traitement général",
        "Calcul SNR a retourné",
        "Fichier source non trouvé pour action",
    )
    offenders = [m for m in markers if m in body]
    assert not offenders, f"French error strings remain: {offenders}"


def test_dead_e_kwargs_removed_from_logic_source():
    body = LOGIC_SOURCE.read_text(encoding="utf-8")
    assert "e='Fichier source" not in body
    assert 'e="Fichier source' not in body


# --------------------------------------------------------------------------- G4
def test_fr_en_key_parity_after_additions():
    fr_keys = set(translations["fr"].keys())
    en_keys = set(translations["en"].keys())
    assert fr_keys == en_keys, (
        f"FR-only: {sorted(fr_keys - en_keys)} | EN-only: {sorted(en_keys - fr_keys)}"
    )


def test_all_new_keys_present_in_both_dictionaries():
    for key in NEW_KEYS:
        assert key in translations["fr"], f"missing FR key: {key}"
        assert key in translations["en"], f"missing EN key: {key}"


def test_new_keys_placeholder_parity():
    mismatches = {}
    for key in NEW_KEYS:
        fr = _placeholders(translations["fr"][key])
        en = _placeholders(translations["en"][key])
        if fr != en:
            mismatches[key] = (sorted(fr), sorted(en))
    assert not mismatches, f"Placeholder mismatch: {mismatches}"
