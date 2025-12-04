"""analysis_model.py

Qt model exposing analysis results rows to QTableView.

This file provides AnalysisResultsModel based on QAbstractTableModel.
The column ordering and canonical keys are read from analysis_schema.get_result_keys().

╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Auteur  : Tinystork, seigneur des couteaux à beurre (aka Tristan Nauleau)       ║
║ Partenaire : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System ║
║              (aka ChatGPT, Grand Maître du ciselage de code)                    ║
║                                                                                 ║
║ Licence : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description :                                                                   ║
║   Ce programme a été forgé à la lueur des pixels et de la caféine,              ║
║   dans le but noble de transformer des nuages de photons en art                 ║
║   astronomique. Si vous l’utilisez, pensez à dire “merci”,                      ║
║   à lever les yeux vers le ciel, ou à citer Tinystork et J.A.R.V.I.S.           ║
║   (le karma des développeurs en dépend).                                        ║
║                                                                                 ║
║ Avertissement :                                                                 ║
║   Aucune IA ni aucun couteau à beurre n’a été blessé durant le                  ║
║   développement de ce code.                                                     ║
╚═════════════════════════════════════════════════════════════════════════════════╝


╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Author  : Tinystork, Lord of the Butter Knives (aka Tristan Nauleau)            ║
║ Partner : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System    ║
║           (aka ChatGPT, Grand Master of Code Chiseling)                         ║
║                                                                                 ║
║ License : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description:                                                                    ║
║   This program was forged under the sacred light of pixels and                  ║
║   caffeine, with the noble intent of turning clouds of photons into             ║
║   astronomical art. If you use it, please consider saying “thanks,”             ║
║   gazing at the stars, or crediting Tinystork and J.A.R.V.I.S. —                ║
║   developer karma depends on it.                                                ║
║                                                                                 ║
║ Disclaimer:                                                                     ║
║   No AIs or butter knives were harmed in the making of this code.               ║
╚════════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations


import os

try:
    from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
    # QColor used to return proper background color in Qt GUI mode
    try:
        from PySide6.QtGui import QColor
    except Exception:
        QColor = None
except Exception:  # pragma: no cover - tests skip when Qt is absent
    Qt = None
    QAbstractTableModel = object
    QModelIndex = object
    QColor = None


class _DummyQt:
    """Minimal Qt stand-in so module import works without PySide6."""

    DisplayRole = 0
    UserRole = 1
    BackgroundRole = 2
    Horizontal = 0
    Vertical = 1


_QT = Qt if Qt is not None else _DummyQt()

import analysis_schema


class AnalysisResultsModel(QAbstractTableModel):
    """A simple table model for analysis results (list of dicts).

    Each row is expected to be a mapping (dict) with keys in
    analysis_schema.get_result_keys(). Missing keys are displayed as empty
    strings.
    """

    def __init__(self, rows=None, parent=None):
        if QAbstractTableModel is object:
            # Running in an environment without Qt - provide a minimal fallback
            # for static analysis/testing scenarios where Qt isn't installed.
            self._rows = rows or []
            self._keys = analysis_schema.get_result_keys()
            return

        super().__init__(parent)
        self._rows = list(rows or [])
        self._keys = analysis_schema.get_result_keys()

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return len(self._keys)

    def data(self, index: QModelIndex, role=_QT.DisplayRole):
        if index is None or not index.isValid():
            return None

        row = self._rows[index.row()]
        key = self._keys[index.column()]
        value = row.get(key, '') if isinstance(row, dict) else ''

        # UserRole should return the raw underlying value (for numeric sorting)
        if role == _QT.UserRole:
            return value

        # Default presentation role returns a string
        if role == _QT.DisplayRole:
            if value is None:
                return ''
            return str(value)

        # Visual decoration / background mapping by indicator (folder/night/bortle)
        try:
            bg_role = _QT.BackgroundRole
        except Exception:
            bg_role = None

        if bg_role is not None and role == bg_role:
            # compute a color for the row based on an indicator value
            indicator = self._compute_indicator_from_row(row)
            if indicator is None:
                return None
            color = self._indicator_color(indicator)
            return color

        return None

    def headerData(self, section: int, orientation, role=_QT.DisplayRole):
        if role != _QT.DisplayRole:
            return None
        if orientation == _QT.Horizontal:
            # return key names as headers for now; UI layer can translate
            keys = self._keys
            if 0 <= section < len(keys):
                return keys[section]
            return None
        if orientation == _QT.Vertical:
            return str(section + 1)

    def get_row(self, idx: int) -> dict:
        return self._rows[idx]

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    # --- visual indicator helpers ---
    def _compute_indicator_from_row(self, row: dict) -> str | None:
        if not isinstance(row, dict):
            return None
        if 'bortle' in row and row.get('bortle') not in (None, ''):
            return f"bortle:{row.get('bortle')}"
        if 'session_date' in row and row.get('session_date'):
            return f"date:{row.get('session_date')}"
        if 'date_obs' in row and row.get('date_obs'):
            return f"date:{row.get('date_obs')[:10]}"
        if 'batch_id' in row and row.get('batch_id'):
            return f"batch:{row.get('batch_id')}"
        path = row.get('file_path') or row.get('path') or row.get('file')
        if path:
            try:
                d = os.path.dirname(path)
                return f"dir:{d or '/'}"
            except Exception:
                return None
        return None

    def _indicator_color(self, indicator: str):
        if not indicator:
            return None

        h = abs(hash(indicator)) % 360
        import colorsys

        r, g, b = colorsys.hls_to_rgb(h / 360.0, 0.85, 0.45)
        rgb = (int(r * 255), int(g * 255), int(b * 255))

        if 'QColor' in globals() and QColor is not None:
            return QColor(*rgb)

        return '#%02x%02x%02x' % rgb


class StackPlanModel(QAbstractTableModel):
    """Model presenting rows from a stacking plan CSV (as produced by stack_plan.py).

    The model accepts either a list of dict rows (matching the CSV headings) or
    a path to a CSV file. The column order mirrors the CSV header and is
    preserved to keep the exact format expected by other tools.
    """

    def __init__(self, rows_or_csv=None, parent=None):
        if QAbstractTableModel is object:
            # fallback minimal implementation (no Qt installed)
            # If a path to a CSV is provided, still attempt to read it so
            # unit tests and non-GUI code can exercise the model.
            if isinstance(rows_or_csv, str):
                import csv
                try:
                    with open(rows_or_csv, "r", encoding="utf-8", newline="") as fh:
                        reader = csv.DictReader(fh)
                        self._keys = list(reader.fieldnames or [])
                        self._rows = [dict(r) for r in reader]
                except Exception:
                    self._rows = []
                    self._keys = []
            else:
                self._rows = list(rows_or_csv or [])
                self._keys = list(self._rows[0].keys()) if self._rows else []
            return

        super().__init__(parent)
        self._rows = []
        self._keys = []

        if rows_or_csv is None:
            return

        # If it's a string assume it's a path to a CSV file
        if isinstance(rows_or_csv, str):
            import csv
            try:
                with open(rows_or_csv, 'r', encoding='utf-8', newline='') as fh:
                    reader = csv.DictReader(fh)
                    self._keys = list(reader.fieldnames or [])
                    self._rows = [dict(r) for r in reader]
            except Exception:
                self._rows = []
                self._keys = []
        else:
            # iterable of dict rows (preserve insertion order of keys)
            self._rows = list(rows_or_csv)
            if self._rows:
                # keep columns in the order of the first row's keys
                self._keys = list(self._rows[0].keys())

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return len(self._keys)

    def data(self, index: QModelIndex, role=_QT.DisplayRole):
        if index is None or not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self._keys[index.column()]
        value = row.get(key, '') if isinstance(row, dict) else ''

        if role == _QT.UserRole:
            return value
        if role == _QT.DisplayRole:
            return '' if value is None else str(value)
        # Support returning background color for an indicator (Qt mode)
        try:
            bg_role = _QT.BackgroundRole
        except Exception:
            bg_role = None

        if bg_role is not None and role == bg_role:
            indicator = self._compute_indicator_from_row(row)
            if indicator is None:
                return None
            return self._indicator_color(indicator)

        return None

    def headerData(self, section: int, orientation, role=_QT.DisplayRole):
        if role != _QT.DisplayRole:
            return None
        if orientation == _QT.Horizontal:
            if 0 <= section < len(self._keys):
                return self._keys[section]
            return None
        if orientation == _QT.Vertical:
            return str(section + 1)

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        if rows:
            self._keys = list(rows[0].keys())
        else:
            self._keys = []
        self.endResetModel()

    # --- visual indicator helpers ---
    def _compute_indicator_from_row(self, row: dict) -> str | None:
        """Return a short indicator key for the row used to decide visuals.

        Priority:
        1. 'bortle' if present
        2. 'session_date' or 'date_obs'
        3. 'batch_id'
        4. directory part of 'file_path' or 'path'

        Returns a string like 'bortle:3' or 'date:2025-01-01'.
        """
        if not isinstance(row, dict):
            return None
        if 'bortle' in row and row.get('bortle') not in (None, ''):
            return f"bortle:{row.get('bortle')}"
        if 'session_date' in row and row.get('session_date'):
            return f"date:{row.get('session_date')}"
        if 'date_obs' in row and row.get('date_obs'):
            # accept full timestamp but normalize to date
            return f"date:{row.get('date_obs')[:10]}"
        if 'batch_id' in row and row.get('batch_id'):
            return f"batch:{row.get('batch_id')}"
        # fall back to directory of file path
        path = row.get('file_path') or row.get('path') or row.get('file')
        if path:
            try:
                d = os.path.dirname(path)
                return f"dir:{d or '/'}"
            except Exception:
                return None
        return None

    def _indicator_color(self, indicator: str):
        """Map indicator to a color.

        In Qt mode returns a QColor; otherwise returns a hex color string.
        The mapping is deterministic but intentionally lightweight: color is
        computed from a hash of the indicator string so identical groups
        share the same color.
        """
        if not indicator:
            return None

        # deterministic hue from indicator text
        h = abs(hash(indicator)) % 360
        # convert HSL-ish to RGB roughly: use hue to produce a pastel color
        # the formula below is a simple approximation mapping hue to an RGB tuple
        # Keep saturation and lightness soft for pleasant pastels
        import colorsys

        r, g, b = colorsys.hls_to_rgb(h / 360.0, 0.85, 0.45)
        rgb = (int(r * 255), int(g * 255), int(b * 255))

        if 'QColor' in globals() and QColor is not None:
            return QColor(*rgb)

        # fallback: return hex string
        return '#%02x%02x%02x' % rgb
