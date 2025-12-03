# Follow-up checklist

## 1. Code audit (cross-platform behavior)
- [x] Search for OS-specific calls and add macOS-safe fallbacks (log openers now use a shared cross-platform helper).
- [ ] Verify Tk/Qt maximization and icon helpers behave correctly on macOS.
- [ ] Continue guarding remaining OS-specific logic and path handling for macOS safety.

## 2. Dependencies and backends
- [x] Make optional features graceful when deps are missing (Bortle/rasterio now reports a clear ImportError instead of crashing).
- [ ] Review requirements for macOS wheels and validate Matplotlib/Tk/Qt backends.

## 3. macOS-specific UI details
- [ ] Confirm window maximization and icon code stay safe on macOS.
- [ ] Validate “open file/folder/log” helpers end-to-end on macOS.

## 4. Automated tests on macOS (CI)
- [x] Add a macOS GitHub Actions workflow that installs deps and runs pytest headlessly.
- [ ] Ensure GUI entrypoints support headless import/execution for CI stability.

## 5. Documentation / README
- [x] Note macOS support and known macOS dependency expectations in the README.
- [ ] Add/expand any macOS known-issues section if new limits are discovered.
