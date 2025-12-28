"""
zeviewer.py - Qt preview widget for ZeAnalyser.

Provides an async image preview with zoom/pan, histogram, stretch,
folder navigation and safe deletion.
"""

from __future__ import annotations

import math
import os
import traceback
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Translations helper (matches zone.py behaviour with graceful fallback)
# ---------------------------------------------------------------------------
try:
    import zone

    _ = zone._
    translations = getattr(zone, "translations", {"en": {}, "fr": {}})
except Exception:  # pragma: no cover - headless fallback
    def _(key, *args, **kwargs):
        return key

    translations = {"en": {}, "fr": {}}


def _tr(key: str, fallback: str) -> str:
    """Translate key when available, otherwise use fallback."""

    try:
        text = _(key)
    except Exception:
        text = key
    # Treat placeholder-style values as missing (e.g., "_key_" or raw key).
    if (text == key or (isinstance(text, str) and text.startswith("_") and text.endswith("_"))) and fallback:
        return fallback
    return text or fallback


# ---------------------------------------------------------------------------
# Optional dependencies (numpy / astropy / PIL)
# ---------------------------------------------------------------------------
try:
    import numpy as np
except Exception:  # pragma: no cover - allows headless import
    np = None

try:
    from astropy.io import fits
except Exception:  # pragma: no cover
    fits = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

# ---------------------------------------------------------------------------
# Qt imports (guarded to allow import without PySide6)
# ---------------------------------------------------------------------------
QT_AVAILABLE = True
try:  # pragma: no cover - GUI runtime only
    from PySide6.QtCore import (
        Qt,
        QSize,
        QObject,
        Signal,
        Slot,
        QRunnable,
        QThreadPool,
        QTimer,
        QPointF,
    )
    from PySide6.QtGui import (
        QImage,
        QPixmap,
        QAction,
        QPainter,
        QColor,
        QPen,
        QPolygonF,
    )
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QGraphicsView,
        QGraphicsScene,
        QGraphicsPixmapItem,
        QToolBar,
        QDoubleSpinBox,
        QPushButton,
        QMessageBox,
        QSizePolicy,
        QFileDialog,
    )
except Exception:  # pragma: no cover - allow import without Qt
    QT_AVAILABLE = False

    class QObject:
        pass

    def Signal(*args, **kwargs):  # type: ignore
        class _Dummy:
            def connect(self, *a, **k):
                return None

            def emit(self, *a, **k):
                return None

        return _Dummy()

    def Slot(*args, **kwargs):  # type: ignore
        def _wrap(func):
            return func

        return _wrap

    class QRunnable:
        def setAutoDelete(self, *_args, **_kwargs):
            return None

        def run(self):
            return None

    class QThreadPool:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self, *_args, **_kwargs):
            return None

        def setMaxThreadCount(self, *_args, **_kwargs):
            return None

    class QWidget:
        pass

    class QGraphicsView:
        pass

    class QGraphicsScene:
        pass

    class QGraphicsPixmapItem:
        pass

    class QVBoxLayout:
        def __init__(self, *_a, **_k):
            pass

        def addWidget(self, *_a, **_k):
            pass

        def addLayout(self, *_a, **_k):
            pass

    class QHBoxLayout(QVBoxLayout):
        pass

    class QLabel:
        def __init__(self, *_a, **_k):
            pass

        def setText(self, *_a, **_k):
            pass

        def setPixmap(self, *_a, **_k):
            pass

        def setMinimumSize(self, *_a, **_k):
            pass

        def setSizePolicy(self, *_a, **_k):
            pass

    class QToolBar:
        def __init__(self, *_a, **_k):
            pass

        def addAction(self, *_a, **_k):
            class _Act:
                def setEnabled(self, *_a, **_k):
                    pass

                def setText(self, *_a, **_k):
                    pass

                def setToolTip(self, *_a, **_k):
                    pass

                def triggered(self, *_a, **_k):
                    pass

            return _Act()

        def addSeparator(self):
            pass

        def setIconSize(self, *_a, **_k):
            pass

    class QDoubleSpinBox:
        def __init__(self, *_a, **_k):
            self._v = 0.0

        def setRange(self, *_a, **_k):
            pass

        def setDecimals(self, *_a, **_k):
            pass

        def setValue(self, v):
            self._v = v

        def value(self):
            return self._v

    class QPushButton:
        def __init__(self, *_a, **_k):
            pass

        def clicked(self, *_a, **_k):  # type: ignore
            pass

        def setText(self, *_a, **_k):
            pass

    class QFileDialog:
        @staticmethod
        def getOpenFileName(*_a, **_k):
            return ("", "")

    class QMessageBox:
        Yes = 0x00004000
        No = 0x00010000

        def __init__(self, *_a, **_k):
            self._cb = None

        def setWindowTitle(self, *_a, **_k):
            pass

        def setText(self, *_a, **_k):
            pass

        def setStandardButtons(self, *_a, **_k):
            pass

        def exec(self):
            return QMessageBox.No

        def setCheckBox(self, cb):
            self._cb = cb

        def checkBox(self):
            return self._cb

    class QSizePolicy:
        Ignored = 0
        Expanding = 1
        Minimum = 2

        def __init__(self, *_a, **_k):
            pass

    class QAction:
        def __init__(self, *_a, **_k):
            self._enabled = True

        def setEnabled(self, enabled: bool):
            self._enabled = enabled

        def setText(self, *_a, **_k):
            pass

        def setToolTip(self, *_a, **_k):
            pass

        def triggered(self, *_a, **_k):
            pass

    class QImage:
        Format_RGB888 = 0
        Format_Grayscale8 = 1

        def __init__(self, *_a, **_k):
            pass

        def copy(self):
            return self

    class QPixmap:
        @staticmethod
        def fromImage(img):
            return img

    class QSize:
        def __init__(self, *_a, **_k):
            pass

    class Qt:  # type: ignore
        KeepAspectRatio = 1
        SmoothTransformation = 0
        StrongFocus = 0
        AnchorUnderMouse = 0
        AnchorViewCenter = 0
        ScrollHandDrag = 0
        Key_Left = 0x01000012
        Key_Right = 0x01000014
        Key_Delete = 0x01000007
        Key_Backspace = 0x01000003
        LeftButton = 1

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------
SUPPORTED_EXTS = (".fit", ".fits", ".fts", ".png", ".jpg", ".jpeg")


class _DummyQtSignal:
    """Small stand-in for Qt signals when running headless."""

    def connect(self, *_args, **_kwargs):
        return None

    def emit(self, *_args, **_kwargs):
        return None


def _is_within_dir(path: str, dir_path: str) -> bool:
    """Return True if path is inside dir_path (case-insensitive on Windows)."""

    if not path or not dir_path:
        return False
    p = os.path.normcase(os.path.realpath(path))
    d = os.path.normcase(os.path.realpath(dir_path))
    try:
        return os.path.commonpath([p, d]) == d
    except ValueError:
        return False


# If Qt or numpy is not available, expose no-op classes to keep imports alive.
if not QT_AVAILABLE or np is None:
    class ZeImageView(QGraphicsView):
        def __init__(self, *_a, **_k):
            super().__init__()

    class ZeHistogramWidget(QWidget):
        sig_levels_changing = _DummyQtSignal()
        sig_levels_changed = _DummyQtSignal()

        def __init__(self, *_a, **_k):
            super().__init__()

        def set_histogram(self, *_a, **_k):
            return None

        def set_levels(self, *_a, **_k):
            return None

    class ZeViewerWidget(QWidget):
        sig_path_navigated = _DummyQtSignal()
        sig_file_deleted = _DummyQtSignal()
        sig_status = _DummyQtSignal()

        def __init__(self, *_a, **_k):
            super().__init__()
            self._last_path = None

        # Public API (no-op)
        def load_path(self, *_a, **_k):
            return None

        def clear(self):
            return None

        def apply_stretch(self, *_a, **_k):
            return None

        def go_prev(self):
            return None

        def go_next(self):
            return None

        def delete_current(self):
            return None

        def retranslate_ui(self):
            return None

    # Nothing else to define when Qt is missing
else:
    # -----------------------------------------------------------------------
    # Worker runnable
    # -----------------------------------------------------------------------
    class PreviewLoadSignals(QObject):
        result = Signal(dict)


    class PreviewLoadRunnable(QRunnable):
        """Worker that loads and downsamples an image + optional dir index."""

        def __init__(
            self,
            path: str,
            token: int,
            max_dim: int = 2000,
            sample_max: int = 200000,
            bins: int = 256,
            index_dir: bool = False,
            dir_path: Optional[str] = None,
        ):
            super().__init__()
            self.path = path
            self.token = token
            self.max_dim = max_dim
            self.sample_max = sample_max
            self.bins = bins
            self.index_dir = index_dir
            self.dir_path = dir_path
            self.signals = PreviewLoadSignals()
            try:
                self.setAutoDelete(True)
            except Exception:
                pass

        def run(self):
            payload = {"token": self.token, "path": self.path}
            try:
                linear = self._load_image(self.path)
                if linear is None:
                    payload["error"] = "no_preview"
                    self.signals.result.emit(payload)
                    return

                preview_arr = linear
                wb = None
                if linear.ndim == 3 and linear.shape[2] == 3:
                    wb = _compute_gray_world_gains_rgb(linear, sample_max=self.sample_max)
                    if wb is not None:
                        gains, _medians = wb
                        preview_arr = np.ascontiguousarray(linear * np.asarray(gains, dtype=np.float32))
                        payload["wb_gains"] = gains

                payload["linear_ds"] = preview_arr
                payload["hist_sample"] = _build_hist_sample(preview_arr, self.sample_max)
                payload["stats"] = _compute_stats(payload["hist_sample"])
                payload["hist"] = _compute_histogram(preview_arr, self.bins)
                auto = _compute_auto_levels(payload["hist_sample"])
                payload["auto_lo"], payload["auto_hi"] = auto

                if self.index_dir:
                    payload.update(_index_directory(self.dir_path or os.path.dirname(self.path), self.path))
            except Exception as exc:  # pragma: no cover - defensive
                payload["error"] = f"{exc}"
                payload["traceback"] = traceback.format_exc()
            self.signals.result.emit(payload)

        # Internal helpers -------------------------------------------------
        def _load_image(self, path: str):
            """Load image array as float32 with shape (H,W) or (H,W,3)."""

            lower = (path or "").lower()
            arr = None
            if lower.endswith((".fit", ".fits", ".fts")):
                arr = _load_fits_array(path)
            elif lower.endswith((".png", ".jpg", ".jpeg")):
                arr = _load_pil_array(path)
            if arr is None or np is None:
                return None
            arr = np.ascontiguousarray(arr, dtype=np.float32)
            h, w = arr.shape[:2]
            if self.max_dim and max(h, w) > self.max_dim:
                step = int(math.ceil(max(h, w) / float(self.max_dim)))
                arr = arr[::step, ::step].copy()
            return arr

    # -----------------------------------------------------------------------
    # Graphics view with pan/zoom + key handling
    # -----------------------------------------------------------------------
    class ZeImageView(QGraphicsView):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setScene(QGraphicsScene(self))
            self._pix_item = QGraphicsPixmapItem()
            self.scene().addItem(self._pix_item)
            self._fit_on_resize = True
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setFocusPolicy(Qt.StrongFocus)
            self._has_pixmap = False

        # Public helpers -------------------------------------------------
        def set_pixmap(self, pix: Optional[QPixmap]):
            if pix is None:
                self._pix_item.setPixmap(QPixmap())
                self._has_pixmap = False
                return
            self._pix_item.setPixmap(pix)
            self._has_pixmap = True
            self.fit_in_view()

        def fit_in_view(self):
            if not self._has_pixmap:
                return
            try:
                rect = self._pix_item.boundingRect()
                if rect.isNull():
                    return
                self.fitInView(rect, Qt.KeepAspectRatio)
                self._fit_on_resize = True
            except Exception:
                pass

        def reset_view(self):
            try:
                self.resetTransform()
                self.fit_in_view()
            except Exception:
                pass

        def set_zoom_1_1(self):
            try:
                self.resetTransform()
            except Exception:
                pass

        def zoom_in(self):
            self._scale_view(1.25)

        def zoom_out(self):
            self._scale_view(0.8)

        def _scale_view(self, factor: float):
            if not self._has_pixmap:
                return
            try:
                self.scale(factor, factor)
                self._fit_on_resize = False
            except Exception:
                pass

        # Events ---------------------------------------------------------
        def wheelEvent(self, event):  # noqa: N802 - Qt signature
            if not self._has_pixmap:
                return super().wheelEvent(event)
            try:
                factor = 1.25 if event.angleDelta().y() > 0 else 0.8
                self._scale_view(factor)
                event.accept()
                return
            except Exception:
                pass
            return super().wheelEvent(event)

        def resizeEvent(self, event):  # noqa: N802
            super().resizeEvent(event)
            if self._fit_on_resize:
                self.fit_in_view()

        def mousePressEvent(self, event):  # noqa: N802
            try:
                self.setFocus()
            except Exception:
                pass
            return super().mousePressEvent(event)

        def keyPressEvent(self, event):  # noqa: N802
            handled = False
            try:
                key = event.key()
                viewer = self.parent()
                if key == Qt.Key_Left and hasattr(viewer, "go_prev"):
                    viewer.go_prev()
                    handled = True
                elif key == Qt.Key_Right and hasattr(viewer, "go_next"):
                    viewer.go_next()
                    handled = True
                elif key in (Qt.Key_Delete, Qt.Key_Backspace) and hasattr(viewer, "delete_current"):
                    viewer.delete_current()
                    handled = True
            except Exception:
                handled = False
            if handled:
                try:
                    event.accept()
                    return
                except Exception:
                    pass
            return super().keyPressEvent(event)

    # -----------------------------------------------------------------------
    # Histogram widget (full width with draggable handles)
    # -----------------------------------------------------------------------
    class ZeHistogramWidget(QWidget):
        sig_levels_changing = Signal(float, float)
        sig_levels_changed = Signal(float, float)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._hist = None
            self._lo: Optional[float] = None
            self._hi: Optional[float] = None
            self._drag_handle: Optional[str] = None
            self._grab_radius = 12
            self.setMinimumHeight(120)
            try:
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            except Exception:
                pass

        # Public API ---------------------------------------------------
        def set_histogram(self, hist, lo: Optional[float] = None, hi: Optional[float] = None):
            self._hist = hist
            if lo is not None:
                self._lo = lo
            if hi is not None:
                self._hi = hi
            self.update()

        def set_levels(self, lo: Optional[float], hi: Optional[float]):
            self._lo = lo
            self._hi = hi
            self.update()

        # Internal helpers --------------------------------------------
        def _value_range(self) -> Optional[tuple[float, float]]:
            hist = self._hist if isinstance(self._hist, dict) else None
            edges = hist.get("edges") if hist else None
            if edges is None or len(edges) < 2:
                return None
            try:
                return float(edges[0]), float(edges[-1])
            except Exception:
                return None

        def _value_to_pos(self, value: Optional[float]) -> Optional[int]:
            rng = self._value_range()
            if rng is None or value is None:
                return None
            lo, hi = rng
            span = hi - lo
            if span <= 0:
                return None
            width = max(1, self.width() - 1)
            ratio = (float(value) - lo) / span
            ratio = max(0.0, min(1.0, ratio))
            return int(round(ratio * width))

        def _pos_to_value(self, pos_x: float) -> Optional[float]:
            rng = self._value_range()
            if rng is None:
                return None
            lo, hi = rng
            span = hi - lo
            if span <= 0:
                return None
            width = max(1, self.width() - 1)
            ratio = float(pos_x) / float(width)
            val = lo + span * ratio
            return min(hi, max(lo, val))

        def _pick_handle(self, pos_x: float) -> Optional[str]:
            lo_pos = self._value_to_pos(self._lo)
            hi_pos = self._value_to_pos(self._hi)
            positions = []
            if lo_pos is not None:
                positions.append(("lo", lo_pos))
            if hi_pos is not None:
                positions.append(("hi", hi_pos))
            if not positions:
                return None
            distances = sorted(((abs(pos_x - px), name) for name, px in positions), key=lambda t: t[0])
            closest_dist, handle = distances[0]
            if closest_dist <= self._grab_radius or len(positions) == 1:
                return handle
            return handle

        def _update_handle_value(self, handle: str, pos_x: float, final: bool = False):
            value = self._pos_to_value(pos_x)
            rng = self._value_range()
            if value is None or rng is None:
                return
            lo_edge, hi_edge = rng
            lo = self._lo
            hi = self._hi
            eps = 1e-9
            if lo is not None and hi is not None:
                eps = max(1e-9, abs(hi - lo) * 1e-9)
            if handle == "lo":
                if hi is not None:
                    value = min(value, hi - eps)
                lo = max(lo_edge, value)
            elif handle == "hi":
                if lo is not None:
                    value = max(value, lo + eps)
                hi = min(hi_edge, value)
            self._lo, self._hi = lo, hi
            self.update()
            try:
                if final:
                    self.sig_levels_changed.emit(lo, hi)
                else:
                    self.sig_levels_changing.emit(lo, hi)
            except Exception:
                pass

        # Painting -----------------------------------------------------
        def paintEvent(self, event):  # noqa: N802
            painter = QPainter(self)
            rect = self.rect()
            painter.fillRect(rect, QColor(18, 18, 18))
            hist = self._hist if isinstance(self._hist, dict) else None
            if hist is None or np is None:
                return
            counts = hist.get("counts")
            edges = hist.get("edges")
            if counts is None or edges is None:
                return
            counts_arr = np.asarray(counts)
            if counts_arr.ndim == 1:
                counts_arr = counts_arr[np.newaxis, :]
            if counts_arr.ndim != 2 or counts_arr.shape[1] == 0 or len(edges) < 2:
                return
            edges_arr = np.asarray(edges)
            span = float(edges_arr[-1] - edges_arr[0]) if edges_arr.size >= 2 else 0.0
            if span == 0.0:
                return
            max_count = float(np.max(counts_arr)) or 1.0
            palette = [
                QColor(80, 180, 255),
                QColor(255, 120, 120),
                QColor(120, 220, 120),
            ]
            centers = (edges_arr[:-1] + edges_arr[1:]) / 2.0
            height = max(1, rect.height() - 4)
            base_y = rect.bottom() - 2
            scale = float(height) / max_count if max_count else 1.0

            for idx, row in enumerate(counts_arr):
                if row.size == 0:
                    continue
                pts = []
                for cx, count in zip(centers, row):
                    pos_x = self._value_to_pos(float(cx))
                    if pos_x is None:
                        continue
                    y = base_y - int(round(float(count) * scale))
                    y = max(rect.top() + 1, min(base_y, y))
                    pts.append(QPointF(pos_x, y))
                if len(pts) >= 2:
                    pen = QPen(palette[idx % len(palette)], 1)
                    painter.setPen(pen)
                    painter.drawPolyline(QPolygonF(pts))

            for handle, value, color in (
                ("lo", self._lo, QColor(255, 200, 0)),
                ("hi", self._hi, QColor(255, 160, 0)),
            ):
                pos = self._value_to_pos(value)
                if pos is None:
                    continue
                pen = QPen(color, 2 if self._drag_handle == handle else 1)
                painter.setPen(pen)
                painter.drawLine(pos, rect.top(), pos, rect.bottom())

        # Mouse interaction -------------------------------------------
        def mousePressEvent(self, event):  # noqa: N802
            if event.button() != Qt.LeftButton:
                return super().mousePressEvent(event)
            pos_x = event.position().x() if hasattr(event, "position") else event.x()
            handle = self._pick_handle(float(pos_x))
            if handle is None:
                return super().mousePressEvent(event)
            self._drag_handle = handle
            self._update_handle_value(handle, float(pos_x), final=False)
            try:
                event.accept()
            except Exception:
                pass

        def mouseMoveEvent(self, event):  # noqa: N802
            if self._drag_handle and (event.buttons() & Qt.LeftButton):
                pos_x = event.position().x() if hasattr(event, "position") else event.x()
                self._update_handle_value(self._drag_handle, float(pos_x), final=False)
                try:
                    event.accept()
                    return
                except Exception:
                    pass
            return super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):  # noqa: N802
            if self._drag_handle and event.button() == Qt.LeftButton:
                pos_x = event.position().x() if hasattr(event, "position") else event.x()
                self._update_handle_value(self._drag_handle, float(pos_x), final=True)
                self._drag_handle = None
                try:
                    event.accept()
                    return
                except Exception:
                    pass
            self._drag_handle = None
            return super().mouseReleaseEvent(event)

    # -----------------------------------------------------------------------
    # Main widget (UI + logic)
    # -----------------------------------------------------------------------
    class ZeViewerWidget(QWidget):
        sig_path_navigated = Signal(str)
        sig_file_deleted = Signal(str)
        sig_status = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._active_token = 0
            self._last_path: Optional[str] = None
            self._dir_path: Optional[str] = None
            self._dir_files: list[str] = []
            self._dir_index: int = -1
            self._dir_cache_key: Optional[tuple[str, float, int]] = None
            self._skip_delete_confirm_session = False
            self._linear_ds = None
            self._display_u8 = None
            self._hist_sample = None
            self._auto_lo: Optional[float] = None
            self._auto_hi: Optional[float] = None
            self._hist = None
            self._wb_gains = None
            self._last_open_dir: Optional[str] = None
            self._levels_sync_guard = False
            self._pending_levels: Optional[tuple[float, float]] = None
            self._levels_timer = QTimer(self)
            try:
                self._levels_timer.setInterval(40)
                self._levels_timer.setSingleShot(True)
                self._levels_timer.timeout.connect(self._process_pending_levels)
            except Exception:
                pass
            self._thread_pool = QThreadPool(self)
            try:
                self._thread_pool.setMaxThreadCount(1)
            except Exception:
                pass

            self._build_ui()
            self.retranslate_ui()

        # UI setup ------------------------------------------------------
        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            self.toolbar = QToolBar()
            try:
                self.toolbar.setIconSize(QSize(16, 16))
            except Exception:
                pass

            self.action_prev = QAction(self)
            self.action_prev.triggered.connect(self.go_prev)
            self.toolbar.addAction(self.action_prev)

            self.action_next = QAction(self)
            self.action_next.triggered.connect(self.go_next)
            self.toolbar.addAction(self.action_next)

            self.action_delete = QAction(self)
            self.action_delete.triggered.connect(self.delete_current)
            self.toolbar.addAction(self.action_delete)

            self.action_open = QAction(self)
            self.action_open.triggered.connect(self._open_file_dialog)
            self.toolbar.addAction(self.action_open)

            self.toolbar.addSeparator()

            self.action_fit = QAction(self)
            self.action_fit.triggered.connect(self._fit_view)
            self.toolbar.addAction(self.action_fit)

            self.action_one_to_one = QAction(self)
            self.action_one_to_one.triggered.connect(self._one_to_one)
            self.toolbar.addAction(self.action_one_to_one)

            self.action_zoom_in = QAction(self)
            self.action_zoom_in.triggered.connect(self._zoom_in)
            self.toolbar.addAction(self.action_zoom_in)

            self.action_zoom_out = QAction(self)
            self.action_zoom_out.triggered.connect(self._zoom_out)
            self.toolbar.addAction(self.action_zoom_out)

            self.action_reset = QAction(self)
            self.action_reset.triggered.connect(self._reset_view)
            self.toolbar.addAction(self.action_reset)

            self.action_clear = QAction(self)
            self.action_clear.triggered.connect(self.clear)
            self.toolbar.addAction(self.action_clear)

            layout.addWidget(self.toolbar)

            self.image_view = ZeImageView(self)
            self.image_view.setMinimumSize(320, 240)
            try:
                self.image_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass
            layout.addWidget(self.image_view)

            info_row = QHBoxLayout()
            self.status_label = QLabel("")
            self.stats_label = QLabel("")
            info_row.addWidget(self.status_label)
            info_row.addStretch(1)
            info_row.addWidget(self.stats_label)
            layout.addLayout(info_row)

            self.hist_widget = ZeHistogramWidget(self)
            try:
                self.hist_widget.sig_levels_changing.connect(self._on_hist_levels_changing)
                self.hist_widget.sig_levels_changed.connect(self._on_hist_levels_changed_final)
            except Exception:
                pass
            layout.addWidget(self.hist_widget)

            stretch_row = QHBoxLayout()
            self.stretch_min_label = QLabel("")
            self.stretch_min = QDoubleSpinBox()
            self.stretch_min.setRange(-1e12, 1e12)
            self.stretch_min.setDecimals(6)

            self.stretch_max_label = QLabel("")
            self.stretch_max = QDoubleSpinBox()
            self.stretch_max.setRange(-1e12, 1e12)
            self.stretch_max.setDecimals(6)

            self.stretch_apply = QPushButton("")
            self.stretch_apply.clicked.connect(lambda: self.apply_stretch(self.stretch_min.value(), self.stretch_max.value()))

            stretch_row.addWidget(self.stretch_min_label)
            stretch_row.addWidget(self.stretch_min)
            stretch_row.addWidget(self.stretch_max_label)
            stretch_row.addWidget(self.stretch_max)
            stretch_row.addWidget(self.stretch_apply)
            layout.addLayout(stretch_row)

        # Remaining behaviour defined below (status updates, load, nav, delete)

        # State helpers ---------------------------------------------------
        def _set_status(self, key: str, fallback: str):
            msg = _tr(key, fallback)
            try:
                self.status_label.setText(msg)
            except Exception:
                pass
            try:
                self.sig_status.emit(msg)
            except Exception:
                pass

        def _update_toolbar_state(self):
            has_file = bool(self._last_path)
            has_nav = bool(self._dir_files) and len(self._dir_files) > 1 and self._dir_index >= 0
            for act, enabled in (
                (self.action_prev, has_nav),
                (self.action_next, has_nav),
                (self.action_delete, has_file),
                (self.action_open, True),
                (self.action_fit, has_file),
                (self.action_one_to_one, has_file),
                (self.action_zoom_in, has_file),
                (self.action_zoom_out, has_file),
                (self.action_reset, has_file),
                (self.action_clear, True),
            ):
                try:
                    act.setEnabled(bool(enabled))
                except Exception:
                    pass

        def _update_stats_label(self, stats):
            if not stats:
                try:
                    self.stats_label.setText("")
                except Exception:
                    pass
                return
            try:
                text = _tr(
                    "preview_stats_fmt",
                    "Min:{min}  Max:{max}  Avg:{mean}  Std:{std}",
                ).format(
                    min=f"{stats['min']:.3f}",
                    max=f"{stats['max']:.3f}",
                    mean=f"{stats['mean']:.3f}",
                    std=f"{stats['std']:.3f}",
                )
                self.stats_label.setText(text)
            except Exception:
                try:
                    self.stats_label.setText("")
                except Exception:
                    pass

        def _sync_spinboxes(self, lo: Optional[float], hi: Optional[float]):
            if lo is None or hi is None:
                return
            if getattr(self, "_levels_sync_guard", False):
                return
            self._levels_sync_guard = True
            try:
                self.stretch_min.setValue(float(lo))
                self.stretch_max.setValue(float(hi))
            except Exception:
                pass
            self._levels_sync_guard = False

        def _update_histogram_display(self, hist, lo: Optional[float] = None, hi: Optional[float] = None):
            try:
                self.hist_widget.set_histogram(hist, lo, hi)
            except Exception:
                pass

        def _on_hist_levels_changing(self, lo: float, hi: float):
            if getattr(self, "_levels_sync_guard", False):
                return
            self._sync_spinboxes(lo, hi)
            self._pending_levels = (float(lo), float(hi))
            try:
                if not self._levels_timer.isActive():
                    self._levels_timer.start()
            except Exception:
                # If timer fails (unlikely), fall back to immediate apply
                self.apply_stretch(lo, hi)

        def _on_hist_levels_changed_final(self, lo: float, hi: float):
            self._pending_levels = None
            self._sync_spinboxes(lo, hi)
            self.apply_stretch(lo, hi)

        def _process_pending_levels(self):
            pending = self._pending_levels
            self._pending_levels = None
            if pending is None:
                return
            self.apply_stretch(*pending)

        # Public API ------------------------------------------------------
        def clear(self):
            self._linear_ds = None
            self._display_u8 = None
            self._hist_sample = None
            self._auto_lo = None
            self._auto_hi = None
            self._hist = None
            self._wb_gains = None
            self._last_path = None
            self._dir_index = -1
            self._pending_levels = None
            try:
                self._levels_timer.stop()
            except Exception:
                pass
            try:
                self.image_view.set_pixmap(None)
            except Exception:
                pass
            try:
                self.hist_widget.set_histogram(None, None, None)
                self.stats_label.setText("")
            except Exception:
                pass
            self._set_status("no_preview_selected", "No preview selected.")
            self._update_toolbar_state()

        def load_path(self, path: str):
            try:
                path = os.path.abspath(path)
            except Exception:
                pass
            self._last_path = path
            if not path or not os.path.isfile(path):
                self._set_status("preview_file_missing", "File not found.")
                self._update_toolbar_state()
                return

            self._set_status("preview_loading", "Loading...")
            self._active_token += 1
            token = self._active_token
            dir_path = os.path.dirname(os.path.abspath(path))
            self._last_open_dir = dir_path
            self._dir_path = dir_path
            need_index = self._should_index_dir(dir_path)
            runnable = PreviewLoadRunnable(
                path=path,
                token=token,
                max_dim=2000,
                sample_max=200000,
                bins=256,
                index_dir=need_index,
                dir_path=dir_path,
            )
            runnable.signals.result.connect(self._on_worker_result)
            try:
                self._thread_pool.start(runnable)
            except Exception:
                # Fallback to synchronous execution if pool fails
                runnable.run()

        def apply_stretch(self, lo: Optional[float] = None, hi: Optional[float] = None):
            if self._linear_ds is None or np is None:
                return
            arr = self._linear_ds
            lo_valid = lo is not None and np.isfinite(lo)
            hi_valid = hi is not None and np.isfinite(hi)
            if not lo_valid or not hi_valid or (lo is not None and hi is not None and lo >= hi):
                lo, hi = self._auto_lo, self._auto_hi

            if lo is None or hi is None or lo >= hi:
                self._set_status("preview_failed", "Failed to load preview.")
                return

            try:
                norm = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
                if norm.ndim == 2:
                    disp = (norm * 255.0).astype(np.uint8)
                    disp = np.ascontiguousarray(disp)
                    qimg = QImage(
                        disp.data, disp.shape[1], disp.shape[0], disp.strides[0], QImage.Format_Grayscale8
                    ).copy()
                else:
                    disp = (norm * 255.0).astype(np.uint8)
                    disp = np.ascontiguousarray(disp)
                    qimg = QImage(
                        disp.data,
                        disp.shape[1],
                        disp.shape[0],
                        disp.strides[0],
                        QImage.Format_RGB888,
                    ).copy()
                self._display_u8 = disp
                self.image_view.set_pixmap(QPixmap.fromImage(qimg))
                self._set_status("", "")
                self._update_stats_label(_compute_stats(self._hist_sample))
                self._update_histogram_display(self._hist, lo, hi)
                self._sync_spinboxes(lo, hi)
            except Exception:
                self._set_status("preview_failed", "Failed to load preview.")

        def go_prev(self):
            if not self._dir_files or self._dir_index < 0:
                return
            new_idx = (self._dir_index - 1) % len(self._dir_files)
            new_path = self._dir_files[new_idx]
            self._dir_index = new_idx
            try:
                self.sig_path_navigated.emit(new_path)
            except Exception:
                pass
            self.load_path(new_path)

        def go_next(self):
            if not self._dir_files or self._dir_index < 0:
                return
            new_idx = (self._dir_index + 1) % len(self._dir_files)
            new_path = self._dir_files[new_idx]
            self._dir_index = new_idx
            try:
                self.sig_path_navigated.emit(new_path)
            except Exception:
                pass
            self.load_path(new_path)

        def delete_current(self):
            path = self._last_path
            if not path:
                return
            if not os.path.isfile(path):
                self._set_status("preview_file_missing", "File not found.")
                return
            if not _is_within_dir(path, self._dir_path or os.path.dirname(path)):
                self._set_status("preview_delete_refused", "Delete refused (path not allowed).")
                return

            if not self._skip_delete_confirm_session:
                box = QMessageBox(self)
                box.setWindowTitle(_tr("preview_delete_title", "Delete file"))
                box.setText(_tr("preview_delete_text", "Delete this file?\n{filename}").format(filename=os.path.basename(path)))
                box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                try:
                    box.setButtonText(QMessageBox.Yes, _tr("preview_delete_yes", "Yes"))
                    box.setButtonText(QMessageBox.No, _tr("preview_delete_no", "No"))
                except Exception:
                    pass
                try:
                    from PySide6.QtWidgets import QCheckBox  # type: ignore
                except Exception:
                    QCheckBox = None  # type: ignore
                if QCheckBox:
                    cb = QCheckBox(_tr("preview_delete_checkbox", "Don't show this message again (this session)"))
                    box.setCheckBox(cb)
                result = box.exec()
                try:
                    cb_widget = box.checkBox()
                    if cb_widget is not None and getattr(cb_widget, "isChecked", lambda: False)():
                        self._skip_delete_confirm_session = True
                except Exception:
                    pass
                if result != QMessageBox.Yes:
                    return

            try:
                # drop backing store to avoid lingering locks
                self.image_view.set_pixmap(None)
                self._linear_ds = None
                self._display_u8 = None
                os.remove(path)
            except Exception:
                self._set_status("preview_delete_failed", "Failed to delete.")
                return

            try:
                self.sig_file_deleted.emit(path)
            except Exception:
                pass

            # Update dir list and navigate
            norm = os.path.normcase(os.path.realpath(path))
            self._dir_files = [p for p in self._dir_files if os.path.normcase(os.path.realpath(p)) != norm]
            if self._dir_files:
                if self._dir_index >= len(self._dir_files):
                    self._dir_index = 0
                next_path = self._dir_files[self._dir_index]
                self.load_path(next_path)
            else:
                self.clear()

            try:
                if self._dir_path and os.path.isdir(self._dir_path):
                    self._dir_cache_key = _build_dir_cache_key(self._dir_path, self._dir_files)
            except Exception:
                pass

        def retranslate_ui(self):
            try:
                self.action_prev.setText(_tr("preview_tb_prev", "Previous image"))
                self.action_prev.setToolTip(_tr("preview_tb_prev", "Previous image"))
                self.action_next.setText(_tr("preview_tb_next", "Next image"))
                self.action_next.setToolTip(_tr("preview_tb_next", "Next image"))
                self.action_delete.setText(_tr("preview_tb_delete", "Delete image"))
                self.action_delete.setToolTip(_tr("preview_tb_delete", "Delete image"))
                self.action_open.setText(_tr("preview_open", "Open file"))
                self.action_open.setToolTip(_tr("preview_open", "Open file"))
                self.action_fit.setText(_tr("preview_fit", "Fit"))
                self.action_one_to_one.setText(_tr("preview_1_1", "1:1"))
                self.action_zoom_in.setText(_tr("preview_zoom_in", "Zoom in"))
                self.action_zoom_out.setText(_tr("preview_zoom_out", "Zoom out"))
                self.action_reset.setText(_tr("preview_reset", "Reset"))
                self.action_clear.setText(_tr("preview_clear", "Clear"))
                self.stretch_min_label.setText(_tr("preview_stretch_min", "Stretch min"))
                self.stretch_max_label.setText(_tr("preview_stretch_max", "max"))
                self.stretch_apply.setText(_tr("preview_apply_stretch", "Apply stretch"))
                if self._last_path is None:
                    self._set_status("no_preview_selected", "No preview selected.")
            except Exception:
                pass
            self._update_toolbar_state()

        # Slots -----------------------------------------------------------
        @Slot(dict)
        def _on_worker_result(self, payload: dict):
            if payload.get("token") != self._active_token:
                return
            if payload.get("error"):
                if payload.get("error") == "no_preview":
                    try:
                        self.image_view.set_pixmap(None)
                    except Exception:
                        pass
                    self._linear_ds = None
                    self._hist = None
                    self._pending_levels = None
                    self._update_histogram_display(None)
                    self._set_status("no_preview_selected", "No preview selected.")
                    self._update_toolbar_state()
                    return
                self._set_status("preview_failed", "Failed to load preview.")
                return

            self._linear_ds = payload.get("linear_ds")
            self._hist_sample = payload.get("hist_sample")
            self._auto_lo = payload.get("auto_lo")
            self._auto_hi = payload.get("auto_hi")
            self._hist = payload.get("hist")
            self._wb_gains = payload.get("wb_gains")
            try:
                self._levels_timer.stop()
            except Exception:
                pass
            self._pending_levels = None

            # Update directory cache if provided
            if payload.get("dir_files") is not None:
                self._dir_path = payload.get("dir_path")
                self._dir_files = payload.get("dir_files") or []
                self._dir_index = payload.get("dir_index", -1)
                self._dir_cache_key = payload.get("dir_cache_key") or _build_dir_cache_key(
                    self._dir_path, self._dir_files
                )
            else:
                # best-effort dir info even when not indexed
                if self._last_path:
                    self._dir_path = os.path.dirname(os.path.abspath(self._last_path))
                    self._dir_index = self._dir_files.index(self._last_path) if self._last_path in self._dir_files else -1

            self._update_histogram_display(self._hist, self._auto_lo, self._auto_hi)
            self._sync_spinboxes(self._auto_lo, self._auto_hi)
            self.apply_stretch(self._auto_lo, self._auto_hi)
            self._update_toolbar_state()

        # Internal helpers -------------------------------------------------
        def _fit_view(self):
            try:
                self.image_view.fit_in_view()
            except Exception:
                pass

        def _one_to_one(self):
            try:
                self.image_view.set_zoom_1_1()
            except Exception:
                pass

        def _zoom_in(self):
            try:
                self.image_view.zoom_in()
            except Exception:
                pass

        def _zoom_out(self):
            try:
                self.image_view.zoom_out()
            except Exception:
                pass

        def _reset_view(self):
            try:
                self.image_view.reset_view()
            except Exception:
                pass

        def _open_file_dialog(self):
            try:
                if QFileDialog is None:
                    return
                # 1) Prefer the directory of the currently displayed file
                start_dir = None
                try:
                    if self._last_path:
                        start_dir = os.path.dirname(os.path.abspath(self._last_path))
                except Exception:
                    start_dir = None

                # 2) Fallback to last opened dir / cached dir / cwd
                if not start_dir:
                    start_dir = self._last_open_dir or self._dir_path or os.getcwd()

                # 3) Ensure valid dir
                if not start_dir or not os.path.isdir(start_dir):
                    start_dir = os.getcwd()

                filters = "Images (*.fit *.fits *.fts *.png *.jpg *.jpeg);;All files (*)"
                fname, _ = QFileDialog.getOpenFileName(self, _tr("preview_open", "Open file"), start_dir, filters)
                if fname:
                    try:
                        self._last_open_dir = os.path.dirname(os.path.abspath(fname))
                    except Exception:
                        pass
                    self.load_path(fname)
            except Exception:
                pass

        def _should_index_dir(self, dir_path: Optional[str]) -> bool:
            if not dir_path:
                return False
            try:
                stat = os.stat(dir_path)
                dir_real = os.path.normcase(os.path.realpath(dir_path))
                new_key = (dir_real, getattr(stat, "st_mtime", 0.0), None)
                if self._dir_cache_key is None:
                    return True
                cached_dir, cached_mtime, _ = self._dir_cache_key
                if cached_dir != dir_real:
                    return True
                if abs(cached_mtime - new_key[1]) > 1e-6:
                    return True
                return False
            except Exception:
                return True


# ---------------------------------------------------------------------------
# Pure helpers (shared by worker)
# ---------------------------------------------------------------------------
def _debayer_preview_2x2(raw: np.ndarray, pattern: str):
    if np is None or raw is None:
        return None
    try:
        if raw.ndim != 2:
            return None
        h2 = (raw.shape[0] // 2) * 2
        w2 = (raw.shape[1] // 2) * 2
        if h2 < 2 or w2 < 2:
            return None

        pat = (pattern or "").strip().upper()
        if pat not in {"RGGB", "BGGR", "GRBG", "GBRG"}:
            return None

        raw_even = raw[:h2, :w2]
        top_left = raw_even[0:h2:2, 0:w2:2]
        top_right = raw_even[0:h2:2, 1:w2:2]
        bottom_left = raw_even[1:h2:2, 0:w2:2]
        bottom_right = raw_even[1:h2:2, 1:w2:2]

        if pat == "RGGB":
            r = top_left
            g1 = top_right
            g2 = bottom_left
            b = bottom_right
        elif pat == "BGGR":
            b = top_left
            g1 = top_right
            g2 = bottom_left
            r = bottom_right
        elif pat == "GRBG":
            g1 = top_left
            r = top_right
            b = bottom_left
            g2 = bottom_right
        else:  # pat == "GBRG"
            g1 = top_left
            b = top_right
            r = bottom_left
            g2 = bottom_right

        g = 0.5 * (g1 + g2)
        return np.stack([r, g, b], axis=-1).astype(np.float32, copy=False)
    except Exception:
        return None


def _pick_first_image_hdu(hdulist):
    try:
        primary = hdulist[0]
        data0 = getattr(primary, "data", None)
        if data0 is not None and np.asarray(data0).ndim >= 2:
            return primary
    except Exception:
        pass

    try:
        for hdu in hdulist:
            try:
                data = getattr(hdu, "data", None)
                if data is None:
                    continue
                if np.asarray(data).ndim >= 2:
                    return hdu
            except Exception:
                continue
    except Exception:
        return None
    return None


def _load_fits_array(path: str):
    if fits is None or np is None:
        return None

    def _open(_memmap: bool):
        try:
            return fits.open(path, memmap=_memmap, lazy_load_hdus=True)
        except TypeError:
            return fits.open(path, memmap=_memmap)

    data = None
    hdu = None

    try:
        # Try memmap=True first (faster when supported)
        with _open(True) as hdulist:
            hdu = _pick_first_image_hdu(hdulist)
            if hdu is not None:
                try:
                    data = getattr(hdu, "data", None)
                except ValueError as e:
                    # Astropy refuses memmap when BZERO/BSCALE/BLANK are present.
                    if "Cannot load a memory-mapped image" in str(e):
                        data = None
                    else:
                        raise

        # Fallback memmap=False if memmap=True failed to load the data
        if data is None:
            with _open(False) as hdulist2:
                hdu = _pick_first_image_hdu(hdulist2)
                if hdu is None:
                    return None
                data = getattr(hdu, "data", None)
                if data is None:
                    return None

        arr = np.array(data, dtype=np.float32, copy=True)
        arr = np.squeeze(arr)

        try:
            bayer = hdu.header.get("BAYERPAT")
        except Exception:
            bayer = None
        if arr.ndim == 2 and bayer:
            rgb = _debayer_preview_2x2(arr, str(bayer))
            if rgb is not None:
                arr = rgb

    except Exception:
        if os.environ.get("ZE_VIEWER_DEBUG", "").strip() not in ("", "0", "false", "False"):
            traceback.print_exc()
        return None
    return _normalize_image_array(arr)


def _load_pil_array(path: str):
    if Image is None or np is None:
        return None
    try:
        with Image.open(path) as im:
            im.load()
            if im.mode == "L":
                arr = np.array(im, dtype=np.float32, copy=True)
            else:
                arr = np.array(im.convert("RGB"), dtype=np.float32, copy=True)
    except Exception:
        return None
    return _normalize_image_array(arr)


def _normalize_image_array(arr):
    if np is None:
        return None
    if arr is None:
        return None
    if arr.ndim == 2:
        return np.array(arr, dtype=np.float32, copy=True)
    if arr.ndim == 3:
        if arr.shape[0] == 3 and arr.shape[1] != 3:
            arr = np.transpose(arr, (1, 2, 0))
        if arr.shape[2] == 3:
            return np.array(arr, dtype=np.float32, copy=True)
    return None


def _compute_gray_world_gains_rgb(arr_rgb, sample_max: int = 200000):
    """Compute simple gray-world gains for RGB arrays (preview only)."""

    if np is None or arr_rgb is None or arr_rgb.ndim != 3 or arr_rgb.shape[2] != 3:
        return None
    try:
        h, w, _ = arr_rgb.shape
        sample = arr_rgb
        if sample_max and h * w > sample_max:
            step = int(math.ceil((h * w) / float(sample_max)))
            sample = arr_rgb[::step, ::step, :]

        medians = []
        for i in range(3):
            channel = sample[:, :, i]
            finite = channel[np.isfinite(channel)]
            medians.append(float(np.median(finite)) if finite.size else float("nan"))

        def _is_valid(val: float) -> bool:
            return np.isfinite(val) and val > 0.0

        target = medians[1] if _is_valid(medians[1]) else None
        if target is None:
            valid = [m for m in medians if _is_valid(m)]
            target = float(np.mean(valid)) if valid else 1.0

        gains = []
        for idx, med in enumerate(medians):
            if idx == 1:
                gains.append(1.0)
                continue
            if _is_valid(med) and _is_valid(target):
                gain = target / med
            else:
                gain = 1.0
            gains.append(float(np.clip(gain, 0.25, 4.0)))
        return tuple(gains), tuple(medians)
    except Exception:
        return None


def _build_hist_sample(arr, sample_max: int):
    if np is None or arr is None:
        return None
    flat = arr.reshape(-1)
    finite = flat[np.isfinite(flat)]
    if finite.size == 0:
        return finite
    if finite.size > sample_max > 0:
        step = int(math.ceil(finite.size / float(sample_max)))
        finite = finite[::step]
    return finite.astype(np.float32, copy=True)


def _compute_stats(sample):
    if np is None or sample is None or getattr(sample, "size", 0) == 0:
        return None
    finite = sample[np.isfinite(sample)]
    if finite.size == 0:
        return None
    return {
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
    }


def _compute_auto_levels(sample):
    if np is None or sample is None or getattr(sample, "size", 0) == 0:
        return (None, None)
    finite = sample[np.isfinite(sample)]
    if finite.size == 0:
        return (None, None)
    try:
        lo, hi = np.percentile(finite, [0.5, 99.5])
        return float(lo), float(hi)
    except Exception:
        return (None, None)


def _compute_histogram(arr, bins: int):
    if np is None or arr is None:
        return None
    try:
        if arr.ndim == 2:
            finite = arr[np.isfinite(arr)]
            counts, edges = np.histogram(finite, bins=bins) if finite.size else (np.zeros(bins, dtype=int), np.linspace(0, 1, bins + 1))
            return {"counts": counts, "edges": edges, "channels": 1}
        if arr.ndim == 3:
            counts_list = []
            edges = None
            for i in range(arr.shape[2]):
                channel = arr[:, :, i]
                finite = channel[np.isfinite(channel)]
                if finite.size:
                    counts, edges = np.histogram(finite, bins=bins)
                else:
                    counts = np.zeros(bins, dtype=int)
                    edges = edges or np.linspace(0, 1, bins + 1)
                counts_list.append(counts)
            return {"counts": np.stack(counts_list, axis=0), "edges": edges, "channels": len(counts_list)}
    except Exception:
        return None
    return None


def _stable_sorted_files(dir_path: str) -> list[str]:
    files: list[str] = []
    try:
        with os.scandir(dir_path) as it:
            for entry in it:
                if entry.is_file() and entry.name.lower().endswith(SUPPORTED_EXTS):
                    files.append(entry.path)
    except Exception:
        return []
    files.sort(key=lambda p: (os.path.basename(p).casefold(), os.path.basename(p)))
    return files


def _index_directory(dir_path: str, current_path: str) -> dict:
    files = _stable_sorted_files(dir_path)
    norm_current = os.path.normcase(os.path.realpath(current_path))
    idx = -1
    for i, p in enumerate(files):
        if os.path.normcase(os.path.realpath(p)) == norm_current:
            idx = i
            break
    return {
        "dir_path": dir_path,
        "dir_files": files,
        "dir_index": idx,
        "dir_cache_key": _build_dir_cache_key(dir_path, files),
    }


def _build_dir_cache_key(dir_path: str, files: Iterable[str]):
    try:
        stat = os.stat(dir_path)
        dir_real = os.path.normcase(os.path.realpath(dir_path))
        return (dir_real, getattr(stat, "st_mtime", 0.0), len(list(files)))
    except Exception:
        return None
