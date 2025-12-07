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
Par la présente, nous adoubons Fabian, Chevalier des pinces à épiler,
pour avoir isolé un cas rarissime et permis d'améliorer l’équilibre ECC / starcount.


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
# Hereby we knight Fabian, Noble Knight of the Tweezers,
# for isolating a rare edge case and helping improve ECC / starcount balance.
 
"""

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.detection import DAOStarFinder

# Default constants for star detection
DEFAULT_THRESHOLD_SIGMA = 5.0
DEFAULT_SHARPLO = 0.2
DEFAULT_SHARPHI = 1.0
DEFAULT_ROUNDLO = -0.6
DEFAULT_ROUNDHI = 0.6


def _detect_stars(
    data: np.ndarray,
    fwhm: float,
    threshold_sigma: float,
    sky_bg: float | None = None,
    sky_noise: float | None = None,
    *,
    sharplo: float = DEFAULT_SHARPLO,
    sharphi: float = DEFAULT_SHARPHI,
    roundlo: float = DEFAULT_ROUNDLO,
    roundhi: float = DEFAULT_ROUNDHI,
):
    """
    Estimate background and noise (unless both provided), then run DAOStarFinder
    with unified parameters. Return (bg, noise, table) where `table` is an
    astropy Table of detections or None.
    """
    bg = sky_bg if sky_bg is not None and np.isfinite(sky_bg) else None
    noise = (
        sky_noise
        if sky_noise is not None and np.isfinite(sky_noise) and sky_noise > 0
        else None
    )

    if bg is None or noise is None:
        _, median, std = sigma_clipped_stats(data, sigma=3.0)
        if bg is None or not np.isfinite(bg):
            bg = median
        if noise is None or not np.isfinite(noise) or noise <= 0:
            noise = std if std > 0 else np.nan

    if not np.isfinite(bg) or not np.isfinite(noise) or noise <= 0:
        return bg, noise, None

    finder = DAOStarFinder(
        fwhm=fwhm,
        threshold=threshold_sigma * noise,
        sharplo=sharplo,
        sharphi=sharphi,
        roundlo=roundlo,
        roundhi=roundhi,
    )
    sources = finder(data - bg)
    return bg, noise, sources if sources is not None and len(sources) > 0 else None


def calculate_fwhm_ecc(
    data,
    fwhm_guess=3.5,
    threshold_sigma=5.0,
    *,
    sky_bg=None,
    sky_noise=None,
    box_radius=4,
):
    """Calculate median FWHM and eccentricity of stars in ``data``.

    Parameters
    ----------
    data : 2-D numpy array
        Image data.
    fwhm_guess : float
        Initial FWHM guess for DAOStarFinder.
    threshold_sigma : float
        Detection threshold in sigma units.
    sky_bg : float, optional
        Pre-computed sky background level. When finite, this value is used
        instead of recomputing it with ``sigma_clipped_stats``.
    sky_noise : float, optional
        Pre-computed sky noise (standard deviation). When finite and positive,
        this value scales the detection threshold without re-running
        ``sigma_clipped_stats``.
    box_radius : int, optional
        Radius of the box around each star for FWHM calculation. Default is 4.

    Returns
    -------
    fwhm_median_px : float
        Median FWHM of detected stars in pixels, or ``np.nan`` if none.
    ecc_median : float
        Median eccentricity of detected stars, or ``np.nan`` if none.
    n_detected : int
        Number of detected stars.
    """
    try:
        bg, _, tbl = _detect_stars(
            data=np.asarray(data),
            fwhm=fwhm_guess,
            threshold_sigma=threshold_sigma,
            sky_bg=sky_bg,
            sky_noise=sky_noise,
        )
        if tbl is None:
            return np.nan, np.nan, 0

        fwhm_list = []
        ecc_list = []

        for star in tbl:
            x_c = star['xcentroid']
            y_c = star['ycentroid']
            x_min = max(int(round(x_c - box_radius)), 0)
            x_max = min(int(round(x_c + box_radius + 1)), data.shape[1])
            y_min = max(int(round(y_c - box_radius)), 0)
            y_max = min(int(round(y_c + box_radius + 1)), data.shape[0])
            cutout = data[y_min:y_max, x_min:x_max]
            if cutout.size == 0:
                continue

            cutout = cutout - bg
            cutout = np.clip(cutout, 0, None)
            total_flux = np.sum(cutout)
            if total_flux <= 0:
                continue

            y_coords, x_coords = np.indices(cutout.shape)
            x_mean = np.sum(x_coords * cutout) / total_flux + x_min
            y_mean = np.sum(y_coords * cutout) / total_flux + y_min

            x_var = np.sum((x_coords - (x_mean - x_min))**2 * cutout) / total_flux
            y_var = np.sum((y_coords - (y_mean - y_min))**2 * cutout) / total_flux
            xy_cov = np.sum((x_coords - (x_mean - x_min)) * (y_coords - (y_mean - y_min)) * cutout) / total_flux

            cov_matrix = np.array([[x_var, xy_cov], [xy_cov, y_var]])
            eigvals = np.linalg.eigvals(cov_matrix)
            sigma_major2 = np.max(eigvals)
            sigma_minor2 = np.min(eigvals)

            fwhm_major = 2.3548 * np.sqrt(sigma_major2)
            fwhm_minor = 2.3548 * np.sqrt(sigma_minor2)
            fwhm_mean = 0.5 * (fwhm_major + fwhm_minor)

            ecc = np.sqrt(1.0 - sigma_minor2 / sigma_major2)

            fwhm_list.append(fwhm_mean)
            ecc_list.append(ecc)

        if not fwhm_list:
            return np.nan, np.nan, 0

        fwhm_med = float(np.nanmedian(fwhm_list))
        ecc_med = float(np.nanmedian(ecc_list))
        n = len(fwhm_list)
        return fwhm_med, ecc_med, n
    except Exception:
        return np.nan, np.nan, 0
