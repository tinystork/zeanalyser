"""analysis_schema.py

Small helper that declares the expected structure/keys of an analysis result
row as produced by analyse_logic.perform_analysis. This will be used by the
Qt model (Phase 3) to present columns in a QTableView.

Keeping these keys here makes it explicit and easy to test and evolve.
"""
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

RESULT_KEYS = [
    'file',
    'path',
    'rel_path',
    'status',
    'action',
    'rejected_reason',
    'action_comment',
    'error_message',
    'has_trails',
    'num_trails',
    'starcount',
    'fwhm',
    'ecc',
    'n_star_ecc',
    'ra',
    'dec',
    'eqmode',
    'sitelong',
    'sitelat',
    'telescope',
    'date_obs',
    # SNR-specific fields
    'snr',
    'sky_bg',
    'sky_noise',
    'signal_pixels',
    'exposure',
    'filter',
    'temperature',
    # Actions / stack plan related (may be filled later)
    'batch_id',
    'order',
]


def get_result_keys():
    """Return the canonical list of result keys in order.

    The Qt table model will use this ordering to generate columns. The list
    intentionally mirrors the shape created in `analyse_logic.perform_analysis`.
    """
    return list(RESULT_KEYS)
