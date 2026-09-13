"""i18n / logging hardening regression tests (mission ZA-I18N-LOGGING-HARDENING-P0.5).

Covers:

* T1 - ``stack_plan_created`` resolves to a real, formatted translation in FR and EN
       (no ``_key_`` / raw-key leakage).
* T2 - FR/EN translation dictionaries have identical key sets (no silent parity drift).
* T3 - every key present in both dictionaries uses the same ``{placeholder}`` set in
       FR and EN (identical ``string.Formatter`` fields).
* T4 - a curated set of active user-facing keys resolves to real translations in
       both languages.
* Source-level guards equivalent to the mission's validation greps:
       no hard-coded ``text=`` French bodies remain in ``analyse_logic.py`` and no
       French developer-diagnostic prints remain.
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
LOGIC_SOURCE = ROOT / "src" / "zeanalyser" / "analyse_logic.py"


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
    """Return the set of ``{field}`` names referenced by a format string."""

    names = set()
    for _literal, field_name, _spec, _conv in string.Formatter().parse(text):
        if field_name:
            names.add(field_name)
    return names


# --------------------------------------------------------------------------- T1
@needs_qt
def test_stack_plan_created_translated_fr_en(lang_restore):
    mod = lang_restore

    mod.set_language("fr")
    fr = mod._("stack_plan_created", path="/tmp/plan.csv")
    assert fr == "Plan de stack créé : /tmp/plan.csv"
    assert "stack_plan_created" not in fr
    assert not fr.startswith("_") and not fr.endswith("_")

    mod.set_language("en")
    en = mod._("stack_plan_created", path="/tmp/plan.csv")
    assert en == "Stacking plan created: /tmp/plan.csv"
    assert "stack_plan_created" not in en
    assert not en.startswith("_") and not en.endswith("_")


# --------------------------------------------------------------------------- T2
def test_fr_en_key_parity():
    fr_keys = set(translations["fr"].keys())
    en_keys = set(translations["en"].keys())
    # No whitelist: the two dictionaries must stay in exact parity.
    assert fr_keys == en_keys, (
        f"FR-only: {sorted(fr_keys - en_keys)} | EN-only: {sorted(en_keys - fr_keys)}"
    )


def test_results_visualisation_title_has_english_translation():
    # Parity fix: this key used to be FR-only and relied on a ``_tr`` fallback.
    assert translations["fr"]["results_visualisation_title"] == "Résultats visuels"
    assert translations["en"]["results_visualisation_title"] == "Results visualisation"


# --------------------------------------------------------------------------- T3
def test_placeholder_compatibility_between_fr_and_en():
    mismatches = {}
    for key in sorted(set(translations["fr"]) & set(translations["en"])):
        fr_names = _placeholders(translations["fr"][key])
        en_names = _placeholders(translations["en"][key])
        if fr_names != en_names:
            mismatches[key] = (sorted(fr_names), sorted(en_names))
    assert not mismatches, f"Placeholder mismatch between FR and EN: {mismatches}"


# --------------------------------------------------------------------------- T4
ACTIVE_KEYS = [
    ("stack_plan_created", {"path": "/tmp/plan.csv"},
     "Plan de stack créé : /tmp/plan.csv", "Stacking plan created: /tmp/plan.csv"),
    ("msg_info", {}, "Information", "Information"),
    ("msg_warning", {}, "Attention", "Warning"),
    ("msg_error", {}, "Erreur", "Error"),
    ("analyse_button", {}, "Analyser les images", "Analyze Images"),
    ("create_stack_plan_button", {}, "Créer plan de stack", "Create stacking plan"),
    ("open_log_button", {}, "Ouvrir le fichier log", "Open Log File"),
    ("logic_input_dir_invalid", {"dir": "/tmp/in"},
     "Dossier d'entrée invalide: /tmp/in", "Invalid input folder: /tmp/in"),
    ("logic_snr_threshold_invalid", {"value": "3.5"},
     "Seuil SNR invalide : '3.5'", "Invalid SNR threshold: '3.5'"),
]


@needs_qt
@pytest.mark.parametrize("key,kwargs,expected_fr,expected_en", ACTIVE_KEYS)
def test_active_keys_resolve_in_both_languages(lang_restore, key, kwargs, expected_fr, expected_en):
    mod = lang_restore

    mod.set_language("fr")
    fr = mod._(key, **kwargs)
    assert fr == expected_fr
    assert not fr.startswith("_") and not fr.endswith("_")

    mod.set_language("en")
    en = mod._(key, **kwargs)
    assert en == expected_en
    assert not en.startswith("_") and not en.endswith("_")


@needs_qt
def test_new_logic_keys_are_translated_not_leaked(lang_restore):
    mod = lang_restore
    sample = [
        "logic_snr_pending_none",
        "logic_trail_pending_none",
        "logic_reco_pending_none",
        "logic_org_none",
        "logic_snr_apply_marking",
        "logic_trail_apply_marking",
        "logic_marker_creation_start",
    ]
    for lang in ("fr", "en"):
        mod.set_language(lang)
        for key in sample:
            resolved = mod._(key)
            assert resolved, key
            assert not resolved.startswith("_") and not resolved.endswith("_"), (lang, key, resolved)


# --------------------------------------------------------------- source guards
def test_no_hardcoded_text_bodies_remain_in_analyse_logic():
    body = LOGIC_SOURCE.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in body.splitlines()
        if "text=" in line
    ]
    assert not offenders, f"Hard-coded text= bodies remain: {offenders}"


def test_no_french_developer_diagnostics_remain_in_analyse_logic():
    body = LOGIC_SOURCE.read_text(encoding="utf-8")
    markers = ("AVERTISSEMENT", "ERREUR CRITIQUE", "Erreur lors de", "Echec pool")
    offenders = [line.strip() for line in body.splitlines() if any(m in line for m in markers)]
    assert not offenders, f"French developer diagnostics remain: {offenders}"
