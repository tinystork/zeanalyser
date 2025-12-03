# -----------------------------------------------------------------------------
# Auteur       : TRISTAN NAULEAU 
# Date         : 2025-07-12
# Licence      : GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
#
# Ce travail est distribué librement en accord avec les termes de la
# GNU GPL v3 (https://www.gnu.org/licenses/gpl-3.0.html).
# Vous êtes libre de redistribuer et de modifier ce code, à condition
# de conserver cette notice et de mentionner que je suis l’auteur
# de tout ou partie du code si vous le réutilisez.
# -----------------------------------------------------------------------------
# Author       : TRISTAN NAULEAU
# Date         : 2025-07-12
# License      : GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
#
# This work is freely distributed under the terms of the
# GNU GPL v3 (https://www.gnu.org/licenses/gpl-3.0.html).
# You are free to redistribute and modify this code, provided that
# you keep this notice and mention that I am the author
# of all or part of the code if you reuse it.
# -----------------------------------------------------------------------------
"""

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
╚═════════════════════════════════════════════════════════════════════════════════╝
"""

import importlib.util
import json
import os
import numpy as np

_rasterio_spec = importlib.util.find_spec("rasterio")
if _rasterio_spec:
    import rasterio
    from rasterio.warp import transform
else:
    rasterio = None
    transform = None

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
    if rasterio is None:
        raise ImportError(
            "rasterio is required to read Bortle atlas files. Install it to enable this feature."
        )
    if not path.lower().endswith(('.tif', '.tiff')):
        raise ValueError("Seuls les fichiers GeoTIFF (.tif/.tiff) sont pris en charge")
    return rasterio.open(path, 'r')


def sample_bortle_dataset(ds, lon: float, lat: float) -> float:
    """Return the sky brightness in \xb5cd/m\xb2 at the given lon/lat."""
    if transform is None:
        raise ImportError(
            "rasterio is required to sample Bortle rasters. Install it to enable this feature."
        )

    if ds.crs and ds.crs.to_string() not in ("EPSG:4326", "WGS84"):
        lon, lat = transform("EPSG:4326", ds.crs, [lon], [lat])
        lon = lon[0]; lat = lat[0]

    raw = list(ds.sample([(lon, lat)]))[0][0]

    tags = ds.tags()
    scale = float(tags.get('scale_factor', 1))
    offset = float(tags.get('add_offset', 0))
    units = tags.get('units', '').lower()
    if units.startswith('cd'):
        mult = 1_000_000
    elif units.startswith('mcd'):
        mult = 1_000
    else:
        mult = 1

    l_ucd = (raw * scale + offset) * mult
    return l_ucd


def ucd_to_sqm(l_ucd: float) -> float:
    """Convertir un éclairement en µcd/m² en mag/arcsec²."""
    return 22.0 - 1.0857 * np.log(l_ucd / 174.0)


def sqm_to_bortle(sqm: float) -> int:
    """Convert an SQM value (mag/arcsec^2) to a Bortle class."""
    for cls, val in sorted(THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if sqm >= val:
            return int(cls)
    return max(THRESHOLDS.keys())


def ucd_to_bortle(l_ucd: float) -> int:
    """Directly convert luminance in µcd/m² to a Bortle class."""
    return sqm_to_bortle(ucd_to_sqm(l_ucd))
