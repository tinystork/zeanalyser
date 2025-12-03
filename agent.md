Mission: Ensure ZeAnalyser is fully compatible with macOS (in addition to Windows and Linux).

Context:
- The project already runs correctly on Windows and Linux.
- I do NOT have a Mac to test manually.
- I need you to:
  1) audit the code for OS-specific behavior,
  2) add proper macOS-safe fallbacks where needed,
  3) wire a CI job that runs our tests on macOS (`macos-latest` GitHub Actions runner),
  so that we have an automated way to validate macOS support.

Scope:
- Tk GUI: `analyse_gui.py`
- Qt GUI: `analyse_gui_qt.py`
- Core modules: `analysis_model.py`, `analysis_schema.py`, `analysis_logic.py`, `bortle_utils.py`, etc.
- Packaging / deps: `requirements.txt`
- Optional: any helper scripts that open files, folders or external viewers.

Tasks (checklist):

1. Code audit (cross-platform behavior)
   - [ ] Search for any OS-specific calls (e.g. `os.startfile`, `subprocess` with Windows-only commands, hard-coded `\\` paths, use of `state("zoomed")`, icon formats, etc.).
   - [ ] Where we already have cross-platform helpers (like maximization and icon handling), verify they behave correctly on macOS:
         - Tk: `safe_set_maximized`, `_set_cross_platform_icon`
         - Qt: window creation, Matplotlib backend (`QtAgg`), use of `QApplication`, etc.
   - [ ] Replace or guard OS-specific logic by using `sys.platform` / `platform.system()` and provide clear fallbacks for macOS (e.g. `open` instead of `start`, avoid assumptions about X11, etc.).
   - [ ] Make sure paths use `os.path.join` / `Path` and never assume Windows separators.

2. Dependencies and backends
   - [ ] Review `requirements.txt` and confirm all packages have wheels for macOS (PySide6, matplotlib, numpy, scipy, rasterio, etc.).
   - [ ] For Matplotlib backends:
         - Tk GUI: confirm `TkAgg` works on macOS.
         - Qt GUI: confirm `QtAgg` is the right backend and does not rely on X11-only plugins.
   - [ ] If some optional features are likely to fail on macOS (e.g. missing system libs for `rasterio`), make them optional:
         - guard the imports,
         - degrade gracefully with a clear user-facing message instead of crashing.

3. macOS-specific UI details
   - [ ] Check window maximization & icon code in Tk and Qt:
         - Make sure the application still starts if the custom icon or zoomed state is not supported on macOS (no hard crash).
   - [ ] Check any “open file / open folder / open log” helpers and ensure they work on macOS:
         - use `subprocess` with `open` when `platform.system() == "Darwin"`.

4. Automated tests on macOS (CI)
   - [ ] Add a GitHub Actions workflow (e.g. `.github/workflows/test-macos.yml`) that:
         - runs on `macos-latest`,
         - sets up Python 3.x,
         - installs our dependencies with `pip install -r requirements.txt`,
         - runs the existing test suite (e.g. `pytest`).
   - [ ] If GUI tests need a headless mode, ensure the Qt and Tk entrypoints support “test mode” / offscreen mode so they can import and run basic logic without a real display.
   - [ ] Make sure the macOS workflow is green locally (by reasoning) and consistent with Windows/Linux workflows.

5. Documentation / README
   - [ ] Update the README to explicitly mention that ZeAnalyser is intended to support Windows, Linux, and macOS.
   - [ ] Add a short “Known issues / macOS” section if there are minor limitations (e.g. some optional features depending on system libs).

Acceptance criteria:
- The codebase contains no obvious Windows-only calls without a macOS fallback.
- GitHub Actions has a `macos-latest` job that installs deps and runs tests successfully.
- Tk and Qt GUIs can at least be imported and their main windows instantiated on macOS without raising platform-specific exceptions.
- README clearly states the multi-platform support and how macOS users should install Python and the required GUI backends.

Please:
- Work by small, focused commits.
- For each change, explain briefly what was done and why (especially for platform checks and CI).
