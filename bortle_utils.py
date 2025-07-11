import os
import json
import rasterio
import numpy as np

THRESHOLD_FILE = os.path.join(os.path.dirname(__file__), 'bortle_thresholds.json')
DEFAULT_THRESHOLDS = {
    "1": 21.9,
    "2": 21.7,
    "3": 21.3,
    "4": 20.9,
    "5": 20.3,
    "6": 19.5,
    "7": 18.8,
    "8": 18.0,
    "9": 0.0
}

def _load_thresholds():
    if os.path.exists(THRESHOLD_FILE):
        try:
            with open(THRESHOLD_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): float(v) for k, v in data.items()}
        except Exception:
            pass
    else:
        try:
            with open(THRESHOLD_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_THRESHOLDS, f, indent=2)
        except Exception:
            pass
    return {int(k): float(v) for k, v in DEFAULT_THRESHOLDS.items()}

THRESHOLDS = _load_thresholds()

def load_bortle_raster(path: str):
    """Open and return a rasterio dataset for the Bortle atlas."""
    if not path.lower().endswith(('.tif', '.tiff')):
        raise ValueError("Seuls les fichiers GeoTIFF (.tif/.tiff) sont pris en charge")
    return rasterio.open(path, 'r')


def ucd_to_sqm(l_ucd: float) -> float:
    """Convertir un éclairement en µcd/m² en mag/arcsec²."""
    return 22.0 - 1.0857 * np.log(l_ucd / 174.0)


def sqm_to_bortle(sqm: float) -> int:
    """Convert an SQM value (mag/arcsec^2) to a Bortle class."""
    for cls, val in sorted(THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if sqm >= val:
            return int(cls)
    return max(THRESHOLDS.keys())
