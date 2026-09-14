from __future__ import annotations

import math

import pytest

from zeanalyser import zeviewer

pytestmark = pytest.mark.skipif(
    not zeviewer.QT_AVAILABLE, reason="PySide6 unavailable"
)


@pytest.fixture
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _loaded_view(qapp):
    from PySide6.QtGui import QPixmap

    view = zeviewer.ZeImageView()
    view.resize(320, 240)
    view.show()
    qapp.processEvents()
    pixmap = QPixmap(640, 320)
    pixmap.fill()
    view.set_pixmap(pixmap)
    qapp.processEvents()
    return view


def _scale(view) -> float:
    return float(view.transform().m11())


def _resize(view, qapp, width, height):
    view.resize(width, height)
    qapp.processEvents()


def test_fit_then_one_to_one_survives_resize(qapp):
    view = _loaded_view(qapp)
    view.fit_in_view()
    assert view._fit_on_resize is True
    assert view._view_mode == "fit"

    view.set_zoom_1_1()
    assert view._fit_on_resize is False
    assert view._view_mode == "one"
    assert math.isclose(_scale(view), 1.0)

    _resize(view, qapp, 480, 360)
    assert view._view_mode == "one"
    assert math.isclose(_scale(view), 1.0)


def test_fit_refits_after_resize(qapp):
    view = _loaded_view(qapp)
    view.fit_in_view()
    before = _scale(view)

    _resize(view, qapp, 600, 420)

    assert view._fit_on_resize is True
    assert view._view_mode == "fit"
    assert not math.isclose(_scale(view), before)


def test_toolbar_manual_zoom_survives_resize_and_transitions(qapp):
    from PySide6.QtGui import QPixmap

    widget = zeviewer.ZeViewerWidget()
    widget.resize(900, 600)
    widget.show()
    pixmap = QPixmap(640, 320)
    pixmap.fill()
    widget.image_view.set_pixmap(pixmap)
    qapp.processEvents()

    widget._fit_view()
    assert widget._session_view_zoom_mode == "fit"
    assert widget.image_view._view_mode == "fit"

    widget._zoom_in()
    manual_scale = _scale(widget.image_view)
    assert widget._session_view_zoom_mode == "manual"
    assert widget.image_view._view_mode == "manual"
    assert widget.image_view._fit_on_resize is False

    _resize(widget.image_view, qapp, 700, 420)
    assert widget._session_view_zoom_mode == "manual"
    assert widget.image_view._view_mode == "manual"
    assert math.isclose(_scale(widget.image_view), manual_scale)

    widget._fit_view()
    assert widget._session_view_zoom_mode == "fit"
    assert widget.image_view._view_mode == "fit"

    widget._one_to_one()
    assert widget._session_view_zoom_mode == "one"
    assert widget.image_view._view_mode == "one"
    assert math.isclose(_scale(widget.image_view), 1.0)


def test_mouse_wheel_manual_zoom_survives_resize(qapp):
    from PySide6.QtCore import QPoint

    class WheelEvent:
        accepted = False

        def angleDelta(self):
            return QPoint(0, 120)

        def accept(self):
            self.accepted = True

    widget = zeviewer.ZeViewerWidget()
    widget.resize(900, 600)
    widget.show()
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(640, 320)
    pixmap.fill()
    widget.image_view.set_pixmap(pixmap)
    widget._fit_view()
    event = WheelEvent()

    widget.image_view.wheelEvent(event)
    manual_scale = _scale(widget.image_view)

    assert event.accepted is True
    assert widget._session_view_zoom_mode == "manual"
    assert widget.image_view._view_mode == "manual"
    assert widget.image_view._fit_on_resize is False
    _resize(widget.image_view, qapp, 680, 400)
    assert math.isclose(_scale(widget.image_view), manual_scale)


def test_one_to_one_session_mode_is_restored_after_new_image(qapp):
    from PySide6.QtGui import QPixmap

    widget = zeviewer.ZeViewerWidget()
    first = QPixmap(640, 320)
    first.fill()
    widget.image_view.set_pixmap(first)
    widget._one_to_one()

    second = QPixmap(320, 640)
    second.fill()
    widget.image_view.set_pixmap(second)  # image loading defaults the raw view to Fit
    assert widget.image_view._view_mode == "fit"
    widget._apply_session_view_zoom()  # same path used after a navigation payload

    assert widget._session_view_zoom_mode == "one"
    assert widget.image_view._view_mode == "one"
    assert widget.image_view._fit_on_resize is False
    assert math.isclose(_scale(widget.image_view), 1.0)


def test_zoom_actions_without_preview_are_harmless(qapp):
    widget = zeviewer.ZeViewerWidget()
    before = _scale(widget.image_view)

    widget._zoom_in()
    widget._zoom_out()
    widget._one_to_one()

    assert math.isclose(_scale(widget.image_view), before)
    assert widget._session_view_zoom_mode == "fit"
    assert widget.image_view._view_mode == "fit"
    assert widget.image_view._fit_on_resize is True
