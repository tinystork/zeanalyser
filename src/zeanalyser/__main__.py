"""``python -m zeanalyser`` entry point — public launch contract.

Stable equivalent of the ``zeanalyser`` gui_script console entry point;
used by external launchers (e.g. ZeMosaic, lot A3).
"""

from zeanalyser.analyse_gui_qt import main

if __name__ == "__main__":
    raise SystemExit(main())
