"""Acceptance gates for ZA-PROJECT-REOPEN-MARKER-CONTRACT-P1."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import string

import pytest

from zeanalyser import __version__, analyse_logic, project_state
import zeanalyser.analyse_gui_qt as gui
from zeanalyser.zone import translations


def _write_log(path: Path, *blocks: object, tail: str = "") -> None:
    with path.open("w", encoding="utf-8") as stream:
        stream.write("log header\n")
        for block in blocks:
            stream.write(project_state.VISUALIZATION_BEGIN + "\n")
            if isinstance(block, str):
                stream.write(block)
            else:
                json.dump(block, stream)
            stream.write("\n" + project_state.VISUALIZATION_END + "\n")
        stream.write(tail)


def _rows(name: str) -> list[dict]:
    return [
        {
            "file": f"{name}.fit",
            "path": f"/{name}.fit",
            "rel_path": f"{name}.fit",
            "status": "ok",
            "action": "kept",
            "rejected_reason": None,
            "snr": 20.0,
            "fwhm": 2.0,
            "ecc": 0.5,
            "starcount": 100,
        }
    ]


# T4/T5 + bounded loader contract
def test_last_complete_valid_visualization_block_wins(tmp_path):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    _write_log(log, _rows("A"), _rows("B"))
    assert project_state.load_latest_valid_visualization_block(log) == _rows("B")


def test_corrupt_or_incomplete_trailing_block_recovers_previous_valid(tmp_path):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    _write_log(
        log,
        _rows("A"),
        "{not valid json",
        tail=project_state.VISUALIZATION_BEGIN + "\n[partial",
    )
    assert project_state.load_latest_valid_visualization_block(log) == _rows("A")


def test_loader_streams_instead_of_using_read_or_readlines(tmp_path, monkeypatch):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    _write_log(log, _rows("A"))
    original_open = Path.open

    class IterOnly:
        def __init__(self, stream):
            self._stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._stream.close()

        def __iter__(self):
            return iter(self._stream)

        def read(self, *_args, **_kwargs):
            raise AssertionError("whole-file read is forbidden")

        def readlines(self, *_args, **_kwargs):
            raise AssertionError("whole-file readlines is forbidden")

    def guarded_open(path, *args, **kwargs):
        return IterOnly(original_open(path, *args, **kwargs))

    monkeypatch.setattr(Path, "open", guarded_open)
    assert project_state.load_latest_valid_visualization_block(log) == _rows("A")


# T7/T9/T10/T11 marker contract
def test_new_marker_schema_timestamp_and_relative_log(tmp_path):
    marker = project_state.write_marker_atomic(
        tmp_path,
        project_state.DEFAULT_LOG_FILENAME,
        completed_at_utc=datetime(2026, 9, 13, 16, 45, tzinfo=timezone.utc),
        product_version="3.4.0",
    )
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert marker.name == "ZeAnalyser.marker.json"
    assert payload == {
        "schema_version": 1,
        "product": "ZeAnalyser",
        "completed_at_utc": "2026-09-13T16:45:00Z",
        "log_file": "analyse_resultats.log",
        "product_version": "3.4.0",
    }
    assert project_state.has_analysis_marker(tmp_path)
    assert not (tmp_path / project_state.LEGACY_MARKER_FILENAME).exists()


def test_atomic_replace_failure_leaves_no_partial_final_marker(tmp_path, monkeypatch):
    def fail_replace(_source, _dest):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        project_state.write_marker_atomic(tmp_path)
    assert not (tmp_path / project_state.NEW_MARKER_FILENAME).exists()
    assert not list(tmp_path.glob(f".{project_state.NEW_MARKER_FILENAME}.*.tmp"))
    assert not project_state.has_analysis_marker(tmp_path)


def test_legacy_marker_is_recognized_without_json(tmp_path):
    legacy = tmp_path / project_state.LEGACY_MARKER_FILENAME
    legacy.write_text("historical marker", encoding="utf-8")
    info = project_state.find_marker(tmp_path)
    assert info is not None and info.legacy
    assert project_state.has_analysis_marker(tmp_path)
    assert project_state.resolve_marker_log_path(tmp_path) is None


def test_dual_marker_cleanup_preserves_unrelated_files(tmp_path):
    project_state.write_marker_atomic(tmp_path)
    (tmp_path / project_state.LEGACY_MARKER_FILENAME).write_text("legacy", encoding="utf-8")
    unrelated = tmp_path / "keep.me"
    unrelated.write_text("safe", encoding="utf-8")
    removed = project_state.remove_markers(tmp_path)
    assert {path.name for path in removed} == {
        project_state.NEW_MARKER_FILENAME,
        project_state.LEGACY_MARKER_FILENAME,
    }
    assert unrelated.read_text(encoding="utf-8") == "safe"
    assert not project_state.marker_paths(tmp_path)


def test_invalid_or_escaping_new_marker_is_not_completion_sentinel(tmp_path):
    marker = tmp_path / project_state.NEW_MARKER_FILENAME
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "ZeAnalyser",
                "completed_at_utc": "2026-09-13T16:45:00Z",
                "log_file": "../../outside.log",
            }
        ),
        encoding="utf-8",
    )
    assert project_state.marker_metadata_invalid(tmp_path)
    assert not project_state.has_analysis_marker(tmp_path)
    assert project_state.resolve_marker_log_path(tmp_path) is None


@pytest.fixture
def window(monkeypatch):
    if gui.QApplication is object:
        pytest.skip("PySide6 unavailable")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = gui.QApplication.instance() or gui.QApplication([])
    win = gui.ZeAnalyserMainWindow()
    yield win
    win.close()
    app.processEvents()


def _select_project(win, path: Path) -> bool:
    win.input_path_edit.setText(str(path))
    win._project_restore_generation = int(getattr(win, "_project_restore_generation", 0)) + 1
    return win._restore_project_state(str(path), emit_diagnostic=True)


# T1/T2/T3/T6 GUI reopen and stale-state gates
def test_fresh_project_has_no_restored_state_and_actions_disabled(tmp_path, window):
    assert _select_project(window, tmp_path) is False
    assert window.analysis_results == []
    assert not window.open_log_btn.isEnabled()
    assert not window.visualise_results_btn.isEnabled()
    assert not window.create_stack_plan_btn.isEnabled()
    assert window.analyse_btn.isEnabled()
    assert window._current_worker is None


def test_project_reopen_supplies_missing_reject_paths_for_future_reanalysis(tmp_path, window):
    window.snr_reject_dir_edit.clear()
    window.trail_reject_dir_edit.clear()
    window._active_project_dir = None
    _select_project(window, tmp_path)
    assert window.snr_reject_dir_edit.text() == str(tmp_path / "rejected_low_snr")
    assert window.trail_reject_dir_edit.text() == str(tmp_path / "rejected_satellite_trails")

    window.analyze_snr_cb.setChecked(True)
    window.reject_move_rb.setChecked(True)
    options = window._build_options_from_ui()
    assert options["snr_reject_dir"] == str(tmp_path / "rejected_low_snr")


def test_existing_valid_project_restores_without_starting_worker(tmp_path, window):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    _write_log(log, _rows("restored"))
    assert _select_project(window, tmp_path) is True
    assert window.analysis_results[0]["file"] == "restored.fit"
    assert window._get_analysis_results_rows()[0]["file"] == "restored.fit"
    assert window.analysis_completed_successfully
    assert window.open_log_btn.isEnabled()
    assert window.visualise_results_btn.isEnabled()
    assert window.create_stack_plan_btn.isEnabled()
    assert window.recommended_images
    assert window._current_worker is None


def test_normal_project_path_signal_restores_without_analysis(tmp_path, window):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    _write_log(log, _rows("signal"))
    window.input_path_edit.setText(str(tmp_path))
    gui.QApplication.processEvents()
    assert window.analysis_results[0]["file"] == "signal.fit"
    assert window._current_worker is None


def test_safe_marker_log_reference_is_used(tmp_path, window):
    nested = tmp_path / "history"
    nested.mkdir()
    custom_log = nested / "prior.log"
    _write_log(custom_log, _rows("custom"))
    project_state.write_marker_atomic(tmp_path, "history/prior.log")
    assert _select_project(window, tmp_path)
    assert window.log_path_edit.text() == str(custom_log)
    assert window.analysis_results[0]["file"] == "custom.fit"


def test_existing_log_without_visualization_keeps_open_log_only(tmp_path, window):
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    log.write_text("ordinary analysis text only\n", encoding="utf-8")
    messages = []
    window._log = messages.append
    assert _select_project(window, tmp_path) is False
    assert window.analysis_results == []
    assert window._get_analysis_results_rows() == []
    assert window.open_log_btn.isEnabled()
    assert not window.visualise_results_btn.isEnabled()
    assert not window.create_stack_plan_btn.isEnabled()
    assert window._current_worker is None
    assert any(str(log) in message for message in messages)


def test_switching_projects_removes_all_stale_results_recommendations_and_plan(tmp_path, window):
    project_a = tmp_path / "A"
    project_b = tmp_path / "B"
    project_a.mkdir()
    project_b.mkdir()
    _write_log(project_a / project_state.DEFAULT_LOG_FILENAME, _rows("A"))
    assert _select_project(window, project_a)
    window.set_stack_plan_rows([{"batch_id": 1, "file": "A.fit"}])
    window._stack_plan_loaded_path = str(project_a / "stack_plan.csv")

    assert not _select_project(window, project_b)
    assert window.analysis_results == []
    assert window._get_analysis_results_rows() == []
    assert window.recommended_images == []
    assert window._stack_plan_loaded_path is None
    assert not window.visualise_results_btn.isEnabled()
    assert not window.create_stack_plan_btn.isEnabled()


def test_marker_management_detects_and_deletes_both_generations_only(tmp_path, window, monkeypatch):
    project_state.write_marker_atomic(tmp_path)
    (tmp_path / project_state.LEGACY_MARKER_FILENAME).write_text("legacy", encoding="utf-8")
    unrelated = tmp_path / "unrelated.marker"
    unrelated.write_text("keep", encoding="utf-8")
    window.input_path_edit.setText(str(tmp_path))
    assert window._has_markers_in_input_dir()

    class Item:
        def text(self):
            return translations["fr"]["marker_project_root_label"]

    class ListWidget:
        def selectedItems(self):
            return [Item()]

        def clear(self):
            pass

        def addItem(self, _item):
            pass

        def setEnabled(self, _enabled):
            pass

    monkeypatch.setattr(gui.QMessageBox, "question", lambda *_args: gui.QMessageBox.Yes)
    monkeypatch.setattr(gui.QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *_args: None)
    window._delete_selected_markers(
        window,
        ListWidget(),
        {translations["fr"]["marker_project_root_label"]: str(tmp_path)},
        str(tmp_path),
        [],
    )
    assert not project_state.marker_paths(tmp_path)
    assert unrelated.read_text(encoding="utf-8") == "keep"


# T8 observable persistence-before-marker ordering
class _ImmediateExecutor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, function, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as error:  # pragma: no cover - defensive
            future.set_exception(error)
        return future


def _analysis_options(root: Path) -> dict:
    return {
        "include_subfolders": False,
        "analyze_snr": False,
        "detect_trails": False,
        "move_rejected": False,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(root),
    }


def _fake_snr(path: str) -> dict:
    return {
        "path": path,
        "snr": 20.0,
        "sky_bg": 1.0,
        "sky_noise": 1.0,
        "signal_pixels": 10,
        "starcount": 5,
        "exposure": 10.0,
        "filter": "LP",
        "temperature": 0.0,
        "eqmode": 2,
        "sitelong": None,
        "sitelat": None,
        "telescope": "Seestar",
        "date_obs": "2026-09-13T16:00:00",
        "error": None,
        "fwhm": 2.0,
        "ecc": 0.5,
        "n_star_ecc": 5,
        "ra": None,
        "dec": None,
    }


def test_marker_is_observably_written_after_resumable_log(tmp_path, monkeypatch):
    (tmp_path / "light.fit").touch()
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", lambda **_kw: _ImmediateExecutor())
    monkeypatch.setattr(analyse_logic, "_snr_worker", _fake_snr)
    real_writer = project_state.write_marker_atomic
    observations = []

    def observe_marker(directory, log_file, **kwargs):
        body = log.read_text(encoding="utf-8")
        observations.append(
            (
                project_state.VISUALIZATION_END in body,
                "Fin du log." in body,
                (tmp_path / "telescopes_pollution.csv").exists(),
            )
        )
        return real_writer(directory, log_file, **kwargs)

    monkeypatch.setattr(project_state, "write_marker_atomic", observe_marker)
    result = analyse_logic.perform_analysis(
        str(tmp_path), str(log), _analysis_options(tmp_path), {}
    )
    assert result
    assert observations == [(True, True, True)]
    assert project_state.has_analysis_marker(tmp_path)


def test_persistence_failure_prevents_new_marker(tmp_path, monkeypatch):
    (tmp_path / "light.fit").touch()
    log = tmp_path / project_state.DEFAULT_LOG_FILENAME
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", lambda **_kw: _ImmediateExecutor())
    monkeypatch.setattr(analyse_logic, "_snr_worker", _fake_snr)
    monkeypatch.setattr(analyse_logic, "write_log_summary", lambda *_args, **_kwargs: False)
    marker_calls = []
    monkeypatch.setattr(project_state, "write_marker_atomic", lambda *_args, **_kwargs: marker_calls.append(True))
    analyse_logic.perform_analysis(str(tmp_path), str(log), _analysis_options(tmp_path), {})
    assert marker_calls == []
    assert not project_state.marker_paths(tmp_path)


# T12 translation parity
def _fields(template: str) -> set[str]:
    return {
        field
        for _literal, field, _spec, _conversion in string.Formatter().parse(template)
        if field
    }


def test_new_translation_keys_and_placeholders_have_fr_en_parity():
    keys = {
        "logic_marker_skipped_persistence_failure",
        "logic_log_finalize_error",
        "marker_scan_error",
        "marker_rescan_error",
        "marker_project_root_label",
        "gui_project_restored",
        "gui_project_log_no_reusable_results",
        "gui_project_marker_invalid",
        "gui_project_restore_failed",
    }
    assert set(translations["fr"]) == set(translations["en"])
    for key in keys:
        assert key in translations["fr"] and key in translations["en"]
        assert _fields(translations["fr"][key]) == _fields(translations["en"][key])


def test_mission_minor_version_bump():
    assert __version__ == "3.4.0"
