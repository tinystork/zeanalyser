import json

import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _build_sample_rows(count: int):
    rows = []
    for idx in range(count):
        rows.append(
            {
                "file": f"image_{idx:03d}.fits",
                "path": f"/data/image_{idx:03d}.fits",
                "rel_path": f"image_{idx:03d}.fits",
                "status": "ok" if idx % 3 else "rejected",
                "action": None,
                "rejected_reason": None,
                "has_trails": bool(idx % 5 == 0),
                "snr": float(idx) if idx % 2 else None,
                "fwhm": None,
                "ecc": None,
                "starcount": None,
            }
        )
    return rows


def test_load_visualisation_from_log_uses_last_block(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    log_path = tmp_path / "analyse_resultats.log"

    rows = _build_sample_rows(30)
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("Début de l'analyse\n")
        fh.write("--- BEGIN VISUALIZATION DATA ---\n")
        json.dump([{"file": "old.fits", "status": "ok"}], fh)
        fh.write("\n--- END VISUALIZATION DATA ---\n")
        fh.write("Autres lignes de log\n")
        fh.write("--- BEGIN VISUALIZATION DATA ---\n")
        json.dump(rows, fh, indent=4)
        fh.write("\n--- END VISUALIZATION DATA ---\n")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    try:
        assert win._load_visualisation_from_log_path(str(log_path)) is True
        assert len(win.analysis_results) == 30
        assert any(r.get("status") == "ok" for r in win.analysis_results)
        assert win._last_loaded_log_path == str(log_path)
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()
