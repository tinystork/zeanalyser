"""ZeAnalyser — standalone analysis module for Seestar light frames.

Sorting and filtering of 'Lights' files to discard low-quality frames and
yield optimal star-field composites. GUI is provided by
``zeanalyser.analyse_gui_qt`` (Qt/PySide6); the historical Tk interface lives
in ``zeanalyser.analyse_gui``.
"""

from zeanalyser._version import __version__

__all__ = ["__version__"]
