from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
import threading
import time

import pytest

from zeanalyser import analyse_logic, project_state
import zeanalyser.analyse_gui_qt as gui
from zeanalyser.zone import translations


def _callbacks(cancel_event: threading.Event, progress: list[float] | None = None):
    progress = progress if progress is not None else []
    return {
        "is_cancelled": cancel_event.is_set,
        "progress": lambda value: progress.append(value),
        "status": lambda *_args, **_kwargs: None,
        "log": lambda *_args, **_kwargs: None,
    }


def _options(root: Path, **overrides):
    options = {
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
    options.update(overrides)
    return options


def _snr_result(path: str, snr: float = 20.0):
    return {
        "path": path,
        "snr": snr,
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
        "date_obs": "2026-09-14T00:00:00",
        "error": None,
        "fwhm": 2.0,
        "ecc": 0.5,
        "n_star_ecc": 5,
        "ra": None,
        "dec": None,
    }


class _ImmediateExecutor:
    def __init__(self, **_kwargs):
        self.shutdown_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.shutdown(wait=True)
        return False

    def submit(self, _function, path):
        future = Future()
        future.set_result(_snr_result(path))
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        self.shutdown_calls.append((wait, cancel_futures))


def _run_with_immediate_snr(tmp_path, monkeypatch, callbacks, options=None):
    (tmp_path / "light.fit").touch()
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _ImmediateExecutor,
    )
    return analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        options or _options(tmp_path),
        callbacks,
    )


def _qt_wait(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        app = gui.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(0.01)
    return condition()


@pytest.fixture
def qapp(monkeypatch):
    if gui.QApplication is object:
        pytest.skip("PySide6 unavailable")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = gui.QApplication.instance() or gui.QApplication([])
    yield app


def test_worker_cancel_is_request_only_and_finishes_once_after_execution(qapp):
    entered = threading.Event()
    observed = threading.Event()
    release = threading.Event()
    finished = []
    results = []
    progress = []

    def blocking_analysis(_input, _output, _options, callbacks):
        entered.set()
        while not callbacks["is_cancelled"]():
            time.sleep(0.005)
        observed.set()
        release.wait(2.0)
        return ["partial"]

    worker = gui.AnalysisWorker()
    worker.finished.connect(finished.append)
    worker.resultsReady.connect(results.append)
    worker.progressChanged.connect(progress.append)
    worker.start(blocking_analysis, "in", "out", {})
    assert entered.wait(1.0)

    assert worker.request_cancel() is True
    assert worker.request_cancel() is False
    assert worker._cancel_event.is_set()
    assert observed.wait(1.0)
    assert finished == []
    assert worker.is_running() is True

    release.set()
    assert _qt_wait(lambda: finished == [True])
    assert worker.is_running() is False
    assert results == []
    assert 100.0 not in progress
    assert worker._thread is not None
    assert worker._thread.isRunning() is False


def test_worker_normal_success_publishes_results_and_100_once(qapp):
    finished = []
    results = []
    progress = []

    def successful(_input, _output, _options, callbacks):
        callbacks["progress"](25)
        return ["ok"]

    worker = gui.AnalysisWorker()
    worker.finished.connect(finished.append)
    worker.resultsReady.connect(results.append)
    worker.progressChanged.connect(progress.append)
    worker.start(successful, "in", "out", {})

    assert _qt_wait(lambda: finished == [False])
    assert results == [["ok"]]
    assert progress[-1] == 100.0
    assert worker._thread.isRunning() is False


def test_window_close_requests_cancel_and_waits_for_worker_stop(qapp, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    close_calls = []

    def blocking_analysis(_input, _output, _options, callbacks):
        entered.set()
        while not callbacks["is_cancelled"]():
            time.sleep(0.005)
        release.wait(2.0)
        return []

    class CloseEvent:
        ignored = False

        def ignore(self):
            self.ignored = True

    window = gui.ZeAnalyserMainWindow()
    worker = gui.AnalysisWorker()
    window._current_worker = worker
    window._connect_worker_signals(worker)
    monkeypatch.setattr(window, "close", lambda: close_calls.append(True))
    worker.start(blocking_analysis, "in", "out", {})
    assert entered.wait(1.0)

    event = CloseEvent()
    window.closeEvent(event)
    assert event.ignored is True
    assert worker._cancel_event.is_set()
    assert worker.is_running() is True
    assert close_calls == []

    release.set()
    assert _qt_wait(lambda: close_calls == [True])
    assert worker.is_running() is False
    assert worker._thread is None


def test_cancel_during_discovery_stops_before_science_and_removes_old_marker(tmp_path, monkeypatch):
    (tmp_path / "light.fit").touch()
    log_path = tmp_path / project_state.DEFAULT_LOG_FILENAME
    log_path.write_text("old complete state", encoding="utf-8")
    project_state.write_marker_atomic(tmp_path, log_path.name, product_version="3.4.0")
    cancel_event = threading.Event()
    progress = []

    real_walk = analyse_logic.os.walk

    def cancelling_walk(root, *args, **kwargs):
        for index, item in enumerate(real_walk(root, *args, **kwargs)):
            if index == 1:
                cancel_event.set()
            yield item
        cancel_event.set()
        yield str(tmp_path / "late"), [], ["late.fit"]

    monkeypatch.setattr(analyse_logic.os, "walk", cancelling_walk)

    class ForbiddenExecutor:
        def __init__(self, **_kwargs):
            raise AssertionError("SNR executor must not start after discovery cancellation")

    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", ForbiddenExecutor)
    result = analyse_logic.perform_analysis(
        str(tmp_path), str(log_path), _options(tmp_path), _callbacks(cancel_event, progress)
    )

    assert result == []
    assert not project_state.marker_paths(tmp_path)
    assert 100 not in progress


def test_cancel_during_snr_cancels_pending_futures_and_waits_for_shutdown(tmp_path, monkeypatch):
    (tmp_path / "a.fit").touch()
    (tmp_path / "b.fit").touch()
    cancel_event = threading.Event()
    instances = []

    class PendingExecutor:
        def __init__(self, **_kwargs):
            self.futures = []
            self.shutdown_calls = []
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.shutdown(wait=True)
            return False

        def submit(self, _function, _path):
            future = Future()
            self.futures.append(future)
            return future

        def shutdown(self, wait=True, *, cancel_futures=False):
            self.shutdown_calls.append((wait, cancel_futures))

    def cancel_before_first_collection(_futures):
        cancel_event.set()
        yield from ()

    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", PendingExecutor)
    monkeypatch.setattr(analyse_logic.concurrent.futures, "as_completed", cancel_before_first_collection)

    result = analyse_logic.perform_analysis(
        str(tmp_path),
        str(tmp_path / project_state.DEFAULT_LOG_FILENAME),
        _options(tmp_path),
        _callbacks(cancel_event),
    )

    executor = instances[0]
    assert result == []
    assert all(future.cancelled() for future in executor.futures)
    assert (True, True) in executor.shutdown_calls
    assert not project_state.marker_paths(tmp_path)


def test_cancel_before_trails_prevents_trail_executor(tmp_path, monkeypatch):
    cancel_event = threading.Event()
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateExecutor)
    monkeypatch.setattr(analyse_logic, "SATDET_AVAILABLE", True)
    monkeypatch.setattr(analyse_logic, "TRAIL_MODULE_LOADED", True)

    class ForbiddenTrailExecutor:
        def __init__(self, **_kwargs):
            raise AssertionError("trail analysis must not start after cancellation")

    monkeypatch.setattr(analyse_logic.concurrent.futures, "ThreadPoolExecutor", ForbiddenTrailExecutor)

    def progress(value):
        if isinstance(value, (int, float)) and value >= 55:
            cancel_event.set()

    result = _run_with_immediate_snr(
        tmp_path,
        monkeypatch,
        {**_callbacks(cancel_event), "progress": progress},
        _options(tmp_path, detect_trails=True),
    )
    assert result == []
    assert not project_state.marker_paths(tmp_path)


def test_cancel_observed_before_destructive_action_starts_none(tmp_path, monkeypatch):
    cancel_event = threading.Event()
    moved = []

    def progress(value):
        if isinstance(value, (int, float)) and value >= 55:
            cancel_event.set()

    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateExecutor)
    monkeypatch.setattr(analyse_logic.shutil, "move", lambda *args: moved.append(args))
    result = _run_with_immediate_snr(
        tmp_path,
        monkeypatch,
        {**_callbacks(cancel_event), "progress": progress},
        _options(
            tmp_path,
            analyze_snr=True,
            snr_selection_mode="threshold",
            snr_selection_value="100",
            move_rejected=True,
            snr_reject_dir=str(tmp_path / "rejected_low_snr"),
            apply_snr_action_immediately=True,
        ),
    )

    assert result == []
    assert moved == []
    assert (tmp_path / "light.fit").is_file()
    assert not project_state.marker_paths(tmp_path)


def test_cancel_racing_with_marker_creation_removes_success_certification(tmp_path, monkeypatch):
    cancel_event = threading.Event()
    progress = []
    real_writer = project_state.write_marker_atomic

    def write_then_cancel(*args, **kwargs):
        marker = real_writer(*args, **kwargs)
        cancel_event.set()
        return marker

    monkeypatch.setattr(project_state, "write_marker_atomic", write_then_cancel)
    result = _run_with_immediate_snr(
        tmp_path, monkeypatch, _callbacks(cancel_event, progress)
    )

    assert result == []
    assert not project_state.marker_paths(tmp_path)
    assert 100 not in progress


def test_cancelled_reanalysis_never_leaves_preexisting_marker_certifying_new_log(tmp_path, monkeypatch):
    (tmp_path / "light.fit").touch()
    log_path = tmp_path / project_state.DEFAULT_LOG_FILENAME
    log_path.write_text("OLD COMPLETE LOG", encoding="utf-8")
    project_state.write_marker_atomic(tmp_path, log_path.name, product_version="3.4.0")
    cancel_event = threading.Event()
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateExecutor)
    real_summary = analyse_logic.write_log_summary

    def persist_then_cancel(*args, **kwargs):
        result = real_summary(*args, **kwargs)
        cancel_event.set()
        return result

    monkeypatch.setattr(analyse_logic, "write_log_summary", persist_then_cancel)
    result = analyse_logic.perform_analysis(
        str(tmp_path), str(log_path), _options(tmp_path), _callbacks(cancel_event)
    )

    assert result == []
    assert not project_state.marker_paths(tmp_path)
    assert "OLD COMPLETE LOG" not in log_path.read_text(encoding="utf-8")


def test_cancellation_messages_have_fr_en_placeholder_parity():
    keys = {
        "status_analysis_cancelling",
        "status_analysis_cancelled",
        "logic_cancellation_requested",
        "logic_analysis_cancelled",
        "logic_reanalysis_marker_invalidated",
        "logic_marker_invalidation_error",
    }
    assert set(translations["fr"]) == set(translations["en"])
    for key in keys:
        assert key in translations["fr"]
        assert key in translations["en"]
