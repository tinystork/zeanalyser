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
        QFontDatabase,
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
        QSplitter,
        QPlainTextEdit,
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
            self._hist = None
            self._lo = None
            self._hi = None
            self._zoom_active = False
            self._zoom_view_lo = None
            self._zoom_view_hi = None

        def set_histogram(self, *_a, **_k):
            return None

        def set_levels(self, *_a, **_k):
            return None

        def is_zoomed(self):
            return bool(self._zoom_active)

        def zoom_to_current_levels(self):
            self._zoom_active = False
            return False

        def zoom_reset(self):
            self._zoom_active = False
            self._zoom_view_lo = None
            self._zoom_view_hi = None

    class ZeViewerWidget(QWidget):
        sig_path_navigated = _DummyQtSignal()
        sig_file_deleted = _DummyQtSignal()
        sig_status = _DummyQtSignal()

        def __init__(self, *_a, **_k):
            super().__init__()
            self._last_path = None
            self._session_active = False
            self._session_levels = None
            self._session_hist_zoom = None
            self._session_view_zoom_mode = "fit"
            self._session_view_scale = 1.0
            self._ui_sync_guard = 0
            self._open_source = "none"
            self._autoload_project_dir = None
            self._autoload_token = 0
            self._display_u8 = None
            self._linear_ds = None

        # Public API (no-op)
        def load_path(self, *_a, **_k):
            return None

        def clear(self):
            return None

        def current_path(self):
            return self._last_path

        def has_image(self):
            return bool(self._last_path)

        def reset_session_state(self, *_a, **_k):
            self._session_active = False
            self._session_levels = None
            self._session_hist_zoom = None
            self._session_view_zoom_mode = "fit"
            self._session_view_scale = 1.0
            self._ui_sync_guard = 0
            self._open_source = "none"
            self._autoload_project_dir = None

        def maybe_autoload_from_project_dir(self, *_a, **_k):
            return False

        def autoload_first_from_dir(self, *_a, **_k):
            return False

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
                linear, header_text = self._load_image(self.path)
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

                payload["header_text"] = header_text
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
            header_text = None
            if lower.endswith((".fit", ".fits", ".fts")):
                arr, header_text = _load_fits_preview_and_header(path)
            elif lower.endswith((".png", ".jpg", ".jpeg")):
                arr = _load_pil_array(path)
            if arr is None or np is None:
                return None, None
            arr = np.ascontiguousarray(arr, dtype=np.float32)
            h, w = arr.shape[:2]
            if self.max_dim and max(h, w) > self.max_dim:
                step = int(math.ceil(max(h, w) / float(self.max_dim)))
                arr = arr[::step, ::step].copy()
            return arr, header_text

    class PickFirstFileSignals(QObject):
        picked = Signal(dict)


    class PickFirstFileRunnable(QRunnable):
        """Worker that finds the first supported file in a directory."""

        def __init__(self, dir_path: str, token: int):
            super().__init__()
            self.dir_path = dir_path
            self.token = token
            self.signals = PickFirstFileSignals()
            try:
                self.setAutoDelete(True)
            except Exception:
                pass

        def run(self):
            payload = {"token": self.token, "dir_path": self.dir_path, "path": None}
            try:
                payload["path"] = self._pick_first_supported()
            except Exception as exc:  # pragma: no cover - defensive
                payload["error"] = f"{exc}"
                payload["traceback"] = traceback.format_exc()
            self.signals.picked.emit(payload)

        def _pick_first_supported(self) -> Optional[str]:
            if not self.dir_path or not os.path.isdir(self.dir_path):
                return None
            first_path = None
            first_key = None
            try:
                with os.scandir(self.dir_path) as it:
                    for entry in it:
                        if not entry.is_file():
                            continue
                        name_lower = entry.name.lower()
                        if not name_lower.endswith(SUPPORTED_EXTS):
                            continue
                        key = (name_lower, entry.name)
                        if first_key is None or key < first_key:
                            first_key = key
                            first_path = entry.path
            except Exception:
                return None
            return first_path

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
                viewer = self.parent()
                try:
                    if viewer is not None and hasattr(viewer, "_on_image_view_scaled"):
                        viewer._on_image_view_scaled()
                except Exception:
                    pass
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
            self._zoom_active: bool = False
            self._zoom_view_lo: Optional[float] = None
            self._zoom_view_hi: Optional[float] = None
            self._drag_handle: Optional[str] = None
            self._grab_radius = 12
            self.setMinimumHeight(120)
            try:
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            except Exception:
                pass

        # Public API ---------------------------------------------------
        def set_histogram(self, hist, lo: Optional[float] = None, hi: Optional[float] = None):
            if hist is None or hist is not self._hist:
                self.zoom_reset()
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

        def is_zoomed(self) -> bool:
            return bool(self._zoom_active)

        def zoom_to_current_levels(self) -> bool:
            hist = self._hist if isinstance(self._hist, dict) else None
            edges = hist.get("edges") if hist else None
            if edges is None or len(edges) < 2:
                return False
            if self._lo is None or self._hi is None:
                return False
            try:
                lo_val = float(self._lo)
                hi_val = float(self._hi)
                edge_lo = float(edges[0])
                edge_hi = float(edges[-1])
            except Exception:
                return False
            if not (
                math.isfinite(lo_val)
                and math.isfinite(hi_val)
                and math.isfinite(edge_lo)
                and math.isfinite(edge_hi)
            ):
                return False
            if lo_val >= hi_val:
                return False
            view_lo = max(edge_lo, lo_val)
            view_hi = min(edge_hi, hi_val)
            if view_lo >= view_hi:
                return False
            self._zoom_active = True
            self._zoom_view_lo = view_lo
            self._zoom_view_hi = view_hi
            self.update()
            return True

        def zoom_reset(self) -> None:
            self._zoom_active = False
            self._zoom_view_lo = None
            self._zoom_view_hi = None
            self.update()

        # Internal helpers --------------------------------------------
        def _value_range(self) -> Optional[tuple[float, float]]:
            hist = self._hist if isinstance(self._hist, dict) else None
            edges = hist.get("edges") if hist else None
            if edges is None or len(edges) < 2:
                return None
            try:
                lo_edge = float(edges[0])
                hi_edge = float(edges[-1])
            except Exception:
                return None
            if self._zoom_active:
                view_lo = self._zoom_view_lo
                view_hi = self._zoom_view_hi
                if (
                    view_lo is not None
                    and view_hi is not None
                    and math.isfinite(view_lo)
                    and math.isfinite(view_hi)
                    and view_lo < view_hi
                ):
                    return view_lo, view_hi
            if not math.isfinite(lo_edge) or not math.isfinite(hi_edge) or lo_edge >= hi_edge:
                return None
            return lo_edge, hi_edge

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
            view_range = self._value_range()
            if view_range is None:
                return
            view_lo, view_hi = view_range
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
            zoom_active = (
                self._zoom_active
                and self._zoom_view_lo is not None
                and self._zoom_view_hi is not None
                and math.isfinite(self._zoom_view_lo)
                and math.isfinite(self._zoom_view_hi)
                and view_lo == self._zoom_view_lo
                and view_hi == self._zoom_view_hi
            )

            for idx, row in enumerate(counts_arr):
                if row.size == 0:
                    continue
                pts = []
                for cx, count in zip(centers, row):
                    if zoom_active and (cx < view_lo or cx > view_hi):
                        continue
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
            self._session_active = False
            self._session_levels: Optional[tuple[float, float]] = None
            self._session_hist_zoom: Optional[bool] = None
            self._session_view_zoom_mode: Optional[str] = "fit"
            self._session_view_scale: float = 1.0
            self._ui_sync_guard = 0
            self._open_source = "none"
            self._autoload_project_dir: Optional[str] = None
            self._autoload_token = 0
            self._linear_ds = None
            self._display_u8 = None
            self._hist_sample = None
            self._auto_lo: Optional[float] = None
            self._auto_hi: Optional[float] = None
            self._hist = None
            self._wb_gains = None
            self._last_open_dir: Optional[str] = None
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

            self.splitter = QSplitter(Qt.Horizontal)
            try:
                self.splitter.setChildrenCollapsible(False)
                self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass

            self.image_view = ZeImageView(self)
            self.image_view.setMinimumSize(320, 240)
            try:
                self.image_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass
            self.splitter.addWidget(self.image_view)

            header_container = QWidget(self)
            header_layout = QVBoxLayout(header_container)
            try:
                header_layout.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            self.header_title = QLabel("")
            self.header_view = QPlainTextEdit()
            self.header_view.setReadOnly(True)
            self.header_view.setUndoRedoEnabled(False)
            self.header_view.setLineWrapMode(QPlainTextEdit.NoWrap)
            try:
                self.header_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
            except Exception:
                pass
            try:
                self.header_view.setMinimumWidth(320)
            except Exception:
                pass
            header_layout.addWidget(self.header_title)
            header_layout.addWidget(self.header_view)
            self.splitter.addWidget(header_container)
            try:
                self.splitter.setStretchFactor(0, 3)
                self.splitter.setStretchFactor(1, 2)
            except Exception:
                pass

            self.vsplitter = QSplitter(Qt.Vertical)
            try:
                self.vsplitter.setChildrenCollapsible(False)
                self.vsplitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass
            self.vsplitter.addWidget(self.splitter)

            self.hist_container = QWidget(self)
            hist_layout = QVBoxLayout(self.hist_container)
            try:
                hist_layout.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass

            info_row = QHBoxLayout()
            self.status_label = QLabel("")
            self.stats_label = QLabel("")
            info_row.addWidget(self.status_label)
            info_row.addStretch(1)
            info_row.addWidget(self.stats_label)
            hist_layout.addLayout(info_row)

            self.hist_widget = ZeHistogramWidget(self)
            try:
                self.hist_widget.sig_levels_changing.connect(self._on_hist_levels_changing)
                self.hist_widget.sig_levels_changed.connect(self._on_hist_levels_changed_final)
            except Exception:
                pass
            hist_layout.addWidget(self.hist_widget)

            stretch_row = QHBoxLayout()
            self.stretch_min_label = QLabel("")
            self.stretch_min = QDoubleSpinBox()
            self.stretch_min.setRange(-1e12, 1e12)
            self.stretch_min.setDecimals(6)

            self.stretch_max_label = QLabel("")
            self.stretch_max = QDoubleSpinBox()
            self.stretch_max.setRange(-1e12, 1e12)
            self.stretch_max.setDecimals(6)
            try:
                self.stretch_min.valueChanged.connect(self._on_spin_levels_changed)
                self.stretch_max.valueChanged.connect(self._on_spin_levels_changed)
            except Exception:
                pass

            self.hist_zoom_btn = QPushButton("")
            self.hist_zoom_btn.clicked.connect(self._toggle_hist_zoom)

            self.stretch_apply = QPushButton("")
            self.stretch_apply.clicked.connect(lambda: self.apply_stretch(self.stretch_min.value(), self.stretch_max.value()))

            stretch_row.addWidget(self.stretch_min_label)
            stretch_row.addWidget(self.stretch_min)
            stretch_row.addWidget(self.stretch_max_label)
            stretch_row.addWidget(self.stretch_max)
            stretch_row.addWidget(self.hist_zoom_btn)
            stretch_row.addWidget(self.stretch_apply)
            hist_layout.addLayout(stretch_row)
            try:
                self.hist_container.setMinimumHeight(220)
            except Exception:
                pass

            self.vsplitter.addWidget(self.hist_container)
            try:
                self.vsplitter.setStretchFactor(0, 4)
                self.vsplitter.setStretchFactor(1, 1)
                self.vsplitter.setSizes([700, 300])
            except Exception:
                pass

            layout.addWidget(self.vsplitter)

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

        def _update_hist_zoom_button(self):
            try:
                zoomed = self.hist_widget.is_zoomed()
            except Exception:
                zoomed = False
            try:
                if zoomed:
                    text = _tr("preview_hist_zoom_reset", "Hist 1:1")
                    tooltip = _tr("preview_hist_zoom_reset_tip", "Reset histogram view")
                else:
                    text = _tr("preview_hist_zoom", "Hist zoom")
                    tooltip = _tr("preview_hist_zoom_tip", "Zoom histogram to current stretch range")
                self.hist_zoom_btn.setText(text)
                self.hist_zoom_btn.setToolTip(tooltip)
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

        def current_path(self) -> Optional[str]:
            return self._last_path

        def has_image(self) -> bool:
            return bool(self._last_path and (self._display_u8 is not None or self._linear_ds is not None))

        def reset_session_state(self, reason: str = "") -> None:
            self._session_active = False
            self._session_levels = None
            self._session_hist_zoom = None
            self._session_view_zoom_mode = "fit"
            self._session_view_scale = 1.0
            self._ui_sync_guard = 0
            self._open_source = "none"
            self._autoload_project_dir = None
            self._pending_levels = None
            try:
                if self._levels_timer.isActive():
                    self._levels_timer.stop()
            except Exception:
                pass
            try:
                self.hist_widget.zoom_reset()
            except Exception:
                pass
            self._update_hist_zoom_button()

        def _update_session_levels(self, lo: Optional[float], hi: Optional[float]):
            if getattr(self, "_ui_sync_guard", 0):
                return
            try:
                lo_val = float(lo) if lo is not None else None
                hi_val = float(hi) if hi is not None else None
            except Exception:
                return
            if lo_val is None or hi_val is None:
                return
            if not math.isfinite(lo_val) or not math.isfinite(hi_val):
                return
            if lo_val >= hi_val:
                return
            self._session_levels = (lo_val, hi_val)
            self._session_active = True

        def _current_view_scale(self) -> Optional[float]:
            try:
                tr = self.image_view.transform()
                scale = float(tr.m11())
                if not math.isfinite(scale):
                    return None
                return abs(scale)
            except Exception:
                return None

        def _update_session_view_zoom(self, mode: str, scale: Optional[float] = None):
            if getattr(self, "_ui_sync_guard", 0):
                return
            self._session_view_zoom_mode = mode
            if scale is not None and math.isfinite(scale) and scale > 0:
                self._session_view_scale = float(scale)
            self._session_active = True

        def _apply_session_view_zoom(self):
            mode = self._session_view_zoom_mode or "fit"
            scale = self._session_view_scale or 1.0
            self._ui_sync_guard += 1
            try:
                if mode == "one":
                    self.image_view.set_zoom_1_1()
                    try:
                        self.image_view._fit_on_resize = False
                    except Exception:
                        pass
                elif mode == "manual":
                    self.image_view.set_zoom_1_1()
                    try:
                        self.image_view._fit_on_resize = False
                    except Exception:
                        pass
                    if scale and math.isfinite(scale) and scale > 0:
                        self.image_view.scale(scale, scale)
                else:
                    self.image_view.fit_in_view()
            except Exception:
                pass
            self._ui_sync_guard = max(0, self._ui_sync_guard - 1)

        def _apply_session_hist_zoom(self):
            zoom_pref = self._session_hist_zoom
            try:
                if zoom_pref is None:
                    self._session_hist_zoom = bool(self.hist_widget.is_zoomed())
                    self._update_hist_zoom_button()
                    return
                if zoom_pref:
                    ok = self.hist_widget.zoom_to_current_levels()
                    if not ok:
                        self.hist_widget.zoom_reset()
                        self._session_hist_zoom = False
                else:
                    self.hist_widget.zoom_reset()
            except Exception:
                pass
            self._update_hist_zoom_button()

        def _on_image_view_scaled(self):
            if getattr(self, "_ui_sync_guard", 0):
                return
            scale = self._current_view_scale()
            if scale is None:
                return
            self._update_session_view_zoom("manual", scale)

        def _on_spin_levels_changed(self, *_args):
            if getattr(self, "_ui_sync_guard", 0):
                return
            lo = None
            hi = None
            try:
                lo = float(self.stretch_min.value())
            except Exception:
                lo = None
            try:
                hi = float(self.stretch_max.value())
            except Exception:
                hi = None
            self._update_session_levels(lo, hi)

        def _sync_spinboxes(self, lo: Optional[float], hi: Optional[float]):
            if lo is None or hi is None:
                return
            if getattr(self, "_ui_sync_guard", 0):
                return
            self._ui_sync_guard += 1
            try:
                self.stretch_min.setValue(float(lo))
                self.stretch_max.setValue(float(hi))
            except Exception:
                pass
            self._ui_sync_guard = max(0, self._ui_sync_guard - 1)

        def _update_histogram_display(self, hist, lo: Optional[float] = None, hi: Optional[float] = None):
            try:
                self.hist_widget.set_histogram(hist, lo, hi)
            except Exception:
                pass

        def _toggle_hist_zoom(self):
            try:
                if getattr(self, "_ui_sync_guard", 0):
                    self._update_hist_zoom_button()
                    return
                if self.hist_widget.is_zoomed():
                    self.hist_widget.zoom_reset()
                else:
                    ok = self.hist_widget.zoom_to_current_levels()
                    if not ok:
                        self._update_hist_zoom_button()
                        return
                self._session_hist_zoom = bool(self.hist_widget.is_zoomed())
                self._session_active = True
                self._update_hist_zoom_button()
            except Exception:
                self._update_hist_zoom_button()

        def _on_hist_levels_changing(self, lo: float, hi: float):
            if getattr(self, "_ui_sync_guard", 0):
                return
            self._update_session_levels(lo, hi)
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
            self._update_session_levels(lo, hi)
            self._sync_spinboxes(lo, hi)
            self.apply_stretch(lo, hi)

        def _process_pending_levels(self):
            pending = self._pending_levels
            self._pending_levels = None
            if pending is None:
                return
            self.apply_stretch(*pending)

        # Public API ------------------------------------------------------
        def _dirs_match(self, a: Optional[str], b: Optional[str]) -> bool:
            if not a or not b:
                return False
            try:
                return _is_within_dir(a, b) and _is_within_dir(b, a)
            except Exception:
                return False

        def maybe_autoload_from_project_dir(self, project_dir: str) -> bool:
            try:
                dir_path = project_dir.strip()
            except Exception:
                dir_path = project_dir
            if not dir_path:
                return False
            try:
                dir_path = os.path.abspath(dir_path)
            except Exception:
                pass
            if not dir_path or not os.path.isdir(dir_path):
                return False
            if not self.has_image():
                return self.autoload_first_from_dir(dir_path, reset_reason="autoload_first")
            if self._open_source == "manual":
                return False
            if self._open_source == "project":
                if self._autoload_project_dir and self._dirs_match(dir_path, self._autoload_project_dir):
                    return False
                return self.autoload_first_from_dir(dir_path, reset_reason="autoload_project_dir_changed")
            return self.autoload_first_from_dir(dir_path, reset_reason="autoload_override")

        def autoload_first_from_dir(self, project_dir: str, reset_reason: str = "autoload_first") -> bool:
            if not project_dir or not os.path.isdir(project_dir):
                return False
            self._autoload_token += 1
            token = self._autoload_token
            runnable = PickFirstFileRunnable(project_dir, token)
            runnable.signals.picked.connect(lambda payload, reason=reset_reason: self._on_autoload_picked(payload, reason))
            try:
                self._thread_pool.start(runnable)
            except Exception:
                runnable.run()
            return True

        def _on_autoload_picked(self, payload: dict, reset_reason: str = "autoload_first"):
            if payload.get("token") != self._autoload_token:
                return
            first_path = payload.get("path")
            if not first_path:
                if not self.has_image():
                    self._set_status("no_preview_selected", "No preview selected.")
                return
            dir_path = payload.get("dir_path") or os.path.dirname(first_path)
            try:
                norm_dir = os.path.abspath(dir_path) if dir_path else dir_path
            except Exception:
                norm_dir = dir_path
            self.reset_session_state(reset_reason)
            self._open_source = "project"
            self._autoload_project_dir = norm_dir
            self.load_path(first_path, source="project", project_dir=norm_dir, index_dir=True)

        def clear(self):
            self.reset_session_state("clear")
            self._linear_ds = None
            self._display_u8 = None
            self._hist_sample = None
            self._auto_lo = None
            self._auto_hi = None
            self._hist = None
            self._wb_gains = None
            self._last_path = None
            self._dir_index = -1
            try:
                self.image_view.set_pixmap(None)
            except Exception:
                pass
            try:
                self.header_view.setPlainText("")
            except Exception:
                pass
            try:
                self.hist_widget.set_histogram(None, None, None)
                self.stats_label.setText("")
            except Exception:
                pass
            self._set_status("no_preview_selected", "No preview selected.")
            self._update_toolbar_state()

        def load_path(
            self,
            path: str,
            source: Optional[str] = None,
            index_dir: Optional[bool] = None,
            project_dir: Optional[str] = None,
        ):
            if source:
                self._open_source = source
                if source == "project":
                    try:
                        self._autoload_project_dir = os.path.abspath(project_dir) if project_dir else project_dir
                    except Exception:
                        self._autoload_project_dir = project_dir
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
            need_index = self._should_index_dir(dir_path) if index_dir is None else bool(index_dir)
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
            except Exception:
                pass
            try:
                self.header_view.setPlainText("")
            except Exception:
                pass
            try:
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
                self.header_title.setText(_tr("preview_header_title", "Header"))
                try:
                    self.header_view.setToolTip(_tr("preview_header_tip", "FITS header for the current image"))
                except Exception:
                    pass
                self.stretch_min_label.setText(_tr("preview_stretch_min", "Stretch min"))
                self.stretch_max_label.setText(_tr("preview_stretch_max", "max"))
                self.stretch_apply.setText(_tr("preview_apply_stretch", "Apply stretch"))
                if self._last_path is None:
                    self._set_status("no_preview_selected", "No preview selected.")
            except Exception:
                pass
            self._update_hist_zoom_button()
            self._update_toolbar_state()

        # Slots -----------------------------------------------------------
        @Slot(dict)
        def _on_worker_result(self, payload: dict):
            if payload.get("token") != self._active_token:
                return
            header_text = payload.get("header_text")
            if payload.get("error"):
                if payload.get("error") == "no_preview":
                    self.reset_session_state("no_preview")
                    try:
                        self.image_view.set_pixmap(None)
                    except Exception:
                        pass
                    try:
                        self.header_view.setPlainText("")
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
                try:
                    self.header_view.setPlainText("")
                except Exception:
                    pass
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
            try:
                self.header_view.setPlainText(header_text or "")
            except Exception:
                pass

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

            def _valid_levels(lo, hi):
                try:
                    lo_f = float(lo)
                    hi_f = float(hi)
                except Exception:
                    return False
                if not math.isfinite(lo_f) or not math.isfinite(hi_f):
                    return False
                return lo_f < hi_f

            target_lo, target_hi = self._auto_lo, self._auto_hi
            if self._session_levels is not None and _valid_levels(*self._session_levels):
                target_lo, target_hi = self._session_levels
            elif _valid_levels(self._auto_lo, self._auto_hi):
                try:
                    self._session_levels = (float(self._auto_lo), float(self._auto_hi))
                    target_lo, target_hi = self._session_levels
                except Exception:
                    pass

            if not self._session_view_zoom_mode:
                self._session_view_zoom_mode = "fit"
            if target_lo is not None and target_hi is not None:
                self._session_active = True
            self._update_histogram_display(self._hist, target_lo, target_hi)
            self._sync_spinboxes(target_lo, target_hi)
            self.apply_stretch(target_lo, target_hi)
            self._apply_session_hist_zoom()
            self._apply_session_view_zoom()
            self._update_toolbar_state()

        # Internal helpers -------------------------------------------------
        def _fit_view(self):
            try:
                self.image_view.fit_in_view()
                self._update_session_view_zoom("fit", 1.0)
            except Exception:
                pass

        def _one_to_one(self):
            try:
                self.image_view.set_zoom_1_1()
                self._update_session_view_zoom("one", 1.0)
            except Exception:
                pass

        def _zoom_in(self):
            try:
                self.image_view.zoom_in()
                self._update_session_view_zoom("manual", self._current_view_scale())
            except Exception:
                pass

        def _zoom_out(self):
            try:
                self.image_view.zoom_out()
                self._update_session_view_zoom("manual", self._current_view_scale())
            except Exception:
                pass

        def _reset_view(self):
            try:
                self.image_view.reset_view()
                self._update_session_view_zoom("fit", 1.0)
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
                    self.reset_session_state("manual_open")
                    self.load_path(fname, source="manual")
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


def _load_fits_preview_and_header(path: str):
    if fits is None or np is None:
        return None, None

    def _open(_memmap: bool):
        try:
            return fits.open(path, memmap=_memmap, lazy_load_hdus=True)
        except TypeError:
            return fits.open(path, memmap=_memmap)

    def _format_header(hdu):
        try:
            return hdu.header.tostring(sep="\n", endcard=False, padding=False)
        except Exception:
            try:
                return str(hdu.header)
            except Exception:
                return None

    data = None
    hdu = None
    header_text = None

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
                header_text = _format_header(hdu)

        # Fallback memmap=False if memmap=True failed to load the data
        if data is None:
            with _open(False) as hdulist2:
                hdu = _pick_first_image_hdu(hdulist2)
                if hdu is None:
                    return None, header_text
                data = getattr(hdu, "data", None)
                if data is None:
                    return None, header_text
                if header_text is None:
                    header_text = _format_header(hdu)

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
        return None, header_text
    return _normalize_image_array(arr), header_text


def _load_fits_array(path: str):
    arr, _header = _load_fits_preview_and_header(path)
    return arr


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
