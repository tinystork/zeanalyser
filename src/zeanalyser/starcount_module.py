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
# Par la présente, nous adoubons Fabian, Chevalier des pinces à épiler,
# pour avoir isolé un cas rarissime et permis d'améliorer l’équilibre ECC / starcount.


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
from zeanalyser.ecc_module import _detect_stars, DEFAULT_THRESHOLD_SIGMA

# Structured star-count outcomes. A measurement failure must never be
# interpreted as a genuine zero-star image (and vice-versa).
OUTCOME_OK = 'ok'
OUTCOME_NO_DETECTIONS = 'no_detections'
OUTCOME_MEASUREMENT_FAILURE = 'measurement_failure'

# Orchestration-level states (produced by analyse_logic, never by the
# measurement itself): the module could not be imported, or starcount analysis
# was not requested for this run. Neither is a measurement failure, and neither
# is a star count of zero.
OUTCOME_UNAVAILABLE = 'unavailable'
OUTCOME_NOT_RUN = 'not_run'


def _starcount_outcome(outcome, count=None, reason=None):
    """Build a picklable structured star-count outcome."""
    return {
        'outcome': outcome,
        'count': None if count is None else int(count),
        'reason': reason,
    }


def calculate_starcount_outcome(
    data,
    fwhm: float = 3.5,
    threshold_sigma: float = DEFAULT_THRESHOLD_SIGMA,
    *,
    sky_bg=None,
    sky_noise=None,
):
    """Structured star-count measurement using DAOStarFinder.

    Returns a picklable dict::

        {'outcome': 'ok'|'no_detections'|'measurement_failure',
         'count': int|None, 'reason': str|None}

    - ``ok``: detections present; ``count`` is the number of stars (>0).
    - ``no_detections``: a genuine absence of detections; ``count`` is 0.
    - ``measurement_failure``: invalid input or an internal exception;
      ``count`` is ``None`` and ``reason`` is a bounded description. This
      must never be treated as a star count of zero.

    Uses the same detection logic as ``calculate_fwhm_ecc_outcome`` to keep
    star selection consistent.
    """
    try:
        arr = np.asarray(data)
        if arr.ndim != 2 or arr.size == 0:
            return _starcount_outcome(
                OUTCOME_MEASUREMENT_FAILURE,
                reason='invalid input: expected a non-empty 2-D array',
            )
        if not np.issubdtype(arr.dtype, np.number) or not np.any(np.isfinite(arr)):
            return _starcount_outcome(
                OUTCOME_MEASUREMENT_FAILURE,
                reason='invalid input: no finite numeric values',
            )

        bg, noise, sources = _detect_stars(
            data=arr,
            fwhm=fwhm,
            threshold_sigma=threshold_sigma,
            sky_bg=sky_bg,
            sky_noise=sky_noise,
        )
        if sources is not None and len(sources) > 0:
            return _starcount_outcome(OUTCOME_OK, count=int(len(sources)))
        # ``sources`` is None for two different reasons: a genuine absence of
        # detections, or an inability to establish valid background/noise
        # statistics (``_detect_stars`` returns non-finite background/noise in
        # that case). Only the former is a real zero-count image.
        if bg is None or noise is None or not np.isfinite(bg) or not np.isfinite(noise) or noise <= 0:
            return _starcount_outcome(
                OUTCOME_MEASUREMENT_FAILURE,
                reason='unable to establish valid background/noise statistics',
            )
        return _starcount_outcome(OUTCOME_NO_DETECTIONS, count=0)
    except Exception as exc:
        return _starcount_outcome(
            OUTCOME_MEASUREMENT_FAILURE,
            reason=('{}: {}'.format(type(exc).__name__, exc))[:250],
        )


def calculate_starcount(
    data,
    fwhm: float = 3.5,
    threshold_sigma: float = DEFAULT_THRESHOLD_SIGMA,
    *,
    sky_bg=None,
    sky_noise=None,
):
    """Return the number of detected stars, or ``None`` on failure.

    Historical wrapper kept practical for existing callers. It returns a
    non-negative integer on success (``0`` for a genuine absence of
    detections) and ``None`` when the measurement failed (invalid input or an
    internal exception), so a failure is never silently reported as zero.
    Callers that need to distinguish outcomes should use
    :func:`calculate_starcount_outcome`.
    """
    outcome = calculate_starcount_outcome(
        data,
        fwhm=fwhm,
        threshold_sigma=threshold_sigma,
        sky_bg=sky_bg,
        sky_noise=sky_noise,
    )
    return outcome['count']
