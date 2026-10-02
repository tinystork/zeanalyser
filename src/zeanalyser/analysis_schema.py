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

import os

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
    'trail_state',
    'trail_error',
    'trail_reason',
    'trail_segments',
    'trail_segment_count',
    'trail_backend_id',
    'trail_backend_version',
    'trail_parameters_effective',
    'starcount',
    'starcount_outcome',
    'starcount_error',
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


# Closed execution states for the trail detector (BASE-03A vocabulary).
TRAIL_STATES = (
    'measured_positive',
    'measured_negative',
    'indeterminate',
    'measurement_failure',
    'skipped',
    'unavailable',
)


def resolve_trail_state(row):
    """Return the effective trail state for a result row (fail-safe).

    The explicit ``trail_state`` field wins. Legacy rows without
    ``trail_state`` map any boolean ``has_trails`` to ``indeterminate``: a
    bare legacy boolean carries no proof of a completed, successful
    measurement.
    """
    if not isinstance(row, dict):
        return 'indeterminate'
    state = row.get('trail_state')
    if state in TRAIL_STATES:
        return state
    return 'indeterminate'


def has_trails_alias(state):
    """Map a trail state to the legacy boolean alias (True/False/None).

    ``True`` only for ``measured_positive``, ``False`` only for
    ``measured_negative``, and ``None`` for every other state.
    """
    if state == 'measured_positive':
        return True
    if state == 'measured_negative':
        return False
    return None


def count_trail_states(rows):
    """Return ``(positive_count, negative_count)`` for trail states.

    Only proven states are counted: ``measured_positive`` and
    ``measured_negative``. Unknown/indeterminate/failure/skipped/unavailable
    rows are never counted as negatives (nor positives). Shared by the Qt and
    Tk visualisation consumers so they cannot diverge.
    """
    pos = 0
    neg = 0
    for row in rows or []:
        state = resolve_trail_state(row)
        if state == 'measured_positive':
            pos += 1
        elif state == 'measured_negative':
            neg += 1
    return pos, neg


def has_measured_or_attempted_trail_state(rows):
    """Return True when any row carries a relevant measured/attempted state.

    ``skipped`` and ``unavailable`` rows alone never activate the trail tab;
    only ``measured_positive``, ``measured_negative``, ``measurement_failure``
    or ``indeterminate`` do.
    """
    relevant = ('measured_positive', 'measured_negative',
                'measurement_failure', 'indeterminate')
    for row in rows or []:
        if resolve_trail_state(row) in relevant:
            return True
    return False


def resolve_row_file_path(row):
    """Resolve the full filesystem path for a result row (shared canonical).

    Supported forms (deterministic, no filesystem dependency):
      * explicit ``file_path`` (full path) — used as-is;
      * canonical ``path`` = complete file path, ``file`` = its basename —
        used as-is (``basename(path) == file``);
      * legacy ``path`` = directory + ``file`` = name — joined.

    The canonical/legacy distinction is decided purely from the row shape:
    when ``path`` already ends with the file name, it is treated as the
    complete file path; otherwise ``path`` is a directory and ``file`` is
    joined into it. This stays correct for a canonical path whose file does
    not exist yet (missing-file witness): ``basename(path)`` still equals
    ``file``, so the path is returned unchanged instead of doubling the
    name into ``path/file/file``.

    Returns ``''`` when no path can be resolved. Never compares a basename
    alone, so distinct directories sharing a basename never conflate.
    """
    try:
        if not isinstance(row, dict):
            return ''
        fp = row.get('file_path')
        if isinstance(fp, str) and fp:
            return fp
        p = row.get('path')
        if not isinstance(p, str) or not p:
            return ''
        f = row.get('file')
        if isinstance(f, str) and f:
            if os.path.basename(p) == f:
                return p
            return os.path.join(p, f)
        return p
    except Exception:
        return ''


def resolve_row_abs_path(row):
    """Absolute canonical path for a result row; '' when unresolvable."""
    p = resolve_row_file_path(row)
    return os.path.abspath(p) if p else ''
