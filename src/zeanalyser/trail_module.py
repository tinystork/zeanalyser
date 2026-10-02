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

import os
import warnings
import inspect
import traceback
import math
import glob

# --- Gestion acstools ---
SATDET_AVAILABLE = False
SATDET_USES_SEARCHPATTERN = False # Garder pour info
# SATDET_ACCEPTS_LIST = False     # Plus nécessaire de tracker spécifiquement

try:
    from acstools import satdet
    if hasattr(satdet, 'detsat') and callable(satdet.detsat):
        sig = inspect.signature(satdet.detsat)
        params = list(sig.parameters)
        first_param_name = params[0] if params else None
        # On vérifie juste si le premier paramètre est celui attendu pour un pattern
        if first_param_name in ['searchpattern', 'input_obj']: # Accepter les deux noms courants
            SATDET_AVAILABLE = True
            SATDET_USES_SEARCHPATTERN = True # On suppose qu'il prend un pattern
            print(f"INFO (trail_module): acstools.satdet.detsat détecté (premier param: '{first_param_name}').")
            # On ne vérifie plus explicitement SATDET_ACCEPTS_LIST ici
        else:
            print(f"AVERTISSEMENT (trail_module): acstools.satdet.detsat trouvé, mais signature ({params}) non attendue. Détection désactivée.")
            SATDET_AVAILABLE = False
    else:
         print("AVERTISSEMENT (trail_module): acstools importé, mais satdet.detsat non trouvé/callable. Détection désactivée.")
except ImportError:
    print("INFO (trail_module): acstools non trouvé. Détection de traînées désactivée.")
except Exception as e:
    print(f"ERREUR (trail_module): Erreur lors de l'import/inspection de acstools.satdet: {e}"); traceback.print_exc()

# --- Dépendances Optionnelles ---
SCIPY_AVAILABLE = False
SKIMAGE_AVAILABLE = False
if SATDET_AVAILABLE:
    import importlib.util
    if importlib.util.find_spec("scipy") is not None:
        SCIPY_AVAILABLE = True
    else:
        print("AVERTISSEMENT (trail_module): scipy non trouvé.")
    if importlib.util.find_spec("skimage") is not None:
        SKIMAGE_AVAILABLE = True
    else:
        print("AVERTISSEMENT (trail_module): scikit-image non trouvé.")

# --- Backend identity (for provenance / per-row trail_backend_* fields) ---
ACSTOOLS_BACKEND_ID = 'acstools.satdet'
ACSTOOLS_BACKEND_VERSION = None
try:
    import acstools as _acstools_pkg
    ACSTOOLS_BACKEND_VERSION = getattr(_acstools_pkg, '__version__', None)
except Exception:
    ACSTOOLS_BACKEND_VERSION = None
if ACSTOOLS_BACKEND_VERSION is None:
    try:
        import importlib.metadata as _importlib_metadata
        ACSTOOLS_BACKEND_VERSION = _importlib_metadata.version('acstools')
    except Exception:
        ACSTOOLS_BACKEND_VERSION = None


def backend_info():
    """Return ``(backend_id, backend_version)`` for the active detector."""
    return (ACSTOOLS_BACKEND_ID, ACSTOOLS_BACKEND_VERSION)


# --- Canonical parameters and normalization primitives ---
TRAIL_PARAM_DEFAULTS = {
    'sigma': 2.0,
    'low_thresh': 0.1,
    'h_thresh': 0.5,
    'line_len': 150,
    'small_edge': 60,
    'line_gap': 75,
}

# Sentinel keys for global (non-file) errors. These are never filesystem paths.
GLOBAL_ERROR_SENTINELS = frozenset({
    'FATAL_ERROR',
    'CONFIG_ERROR',
    'DEPENDENCY_ERROR',
    'IMPORT_ERROR',
    'FATAL_CALL_ERROR',
})


def normalize_detsat_key(key):
    """Normalize a satdet result/error key to a canonical ``(normpath, ext)``.

    Handles both the string form (``'/abs/file.fits'``) and the tuple form
    (``('/abs/file.fits', 0)``). The path is made absolute and normcase'd so a
    single file is keyed identically across results and errors.

    Returns ``None`` when the key cannot be interpreted, including when the
    extension is not convertible to an ``int`` (an invalid extension is never
    silently coerced to ``0``).
    """
    if isinstance(key, tuple) and len(key) == 2:
        path, ext = key
    elif isinstance(key, str):
        path, ext = key, 0
    else:
        return None
    try:
        ext_int = int(ext)
    except (TypeError, ValueError):
        return None
    # Path must be a non-empty str/PathLike; None/empty is never mapped to a
    # probative cwd/... path.
    if not isinstance(path, (str, os.PathLike)) or not str(path).strip():
        return None
    try:
        norm_path = os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        norm_path = os.path.normcase(str(path))
    return (norm_path, ext_int)


def is_global_error_key(key):
    """Return True when a key is a non-file sentinel (fatal/config/etc.).

    Accepts both the tuple form ``('CONFIG_ERROR', 0)`` and the bare string
    form ``'CONFIG_ERROR'``.
    """
    if isinstance(key, str):
        return key.upper() in GLOBAL_ERROR_SENTINELS
    if isinstance(key, tuple) and len(key) == 2 and isinstance(key[0], str):
        return key[0].upper() in GLOBAL_ERROR_SENTINELS
    return False


def segments_to_serializable(segments):
    """Convert satdet segment arrays into JSON-serializable endpoint lists.

    acstools returns an ndarray of shape ``(n, 2, 2)`` (or an empty array for
    no trail).

    Returns ``(segments, error)``:
    - ``segments``: list of ``[[x0, y0], [x1, y1]]`` pairs with plain Python
      numbers, or ``[]`` for an explicit-empty (valid) result.
    - ``error``: ``None`` on success; a bounded message when the input is not
      a valid segment container (None, string/scalar, wrong segment shape,
      non-numeric or non-finite coordinates), so the caller can mark the
      outcome ``indeterminate`` instead of silently treating it as a measured
      negative. Only an explicitly-empty container is a measured negative.
    """
    if segments is None:
        return [], "trail result is None (missing payload)"
    if isinstance(segments, (str, bytes)):
        return [], "trail result is not a segment container"
    try:
        items = list(segments)
    except TypeError:
        return [], "trail result is not iterable"
    if not items:
        return [], None  # explicit empty container -> valid negative
    serializable = []
    for seg in items:
        try:
            (x0, y0), (x1, y1) = seg
        except (TypeError, ValueError):
            return [], "malformed trail segment in result"
        try:
            coords = [float(x0), float(y0), float(x1), float(y1)]
        except (TypeError, ValueError):
            return [], "non-numeric trail segment coordinates"
        if any(not math.isfinite(c) for c in coords):
            return [], "non-finite trail segment coordinates"
        serializable.append([[coords[0], coords[1]], [coords[2], coords[3]]])
    return serializable, None


def bound_message(msg, limit=500):
    """Bound a message string to ``limit`` characters for provenance fields."""
    if msg is None:
        return None
    msg = str(msg)
    if len(msg) <= limit:
        return msg
    return msg[:limit - 3] + '...'


def resolve_trail_params(sat_params_input, log_callback=None):
    """Resolve and validate canonical trail-detection parameters.

    Canonical threshold names are ``low_thresh``/``h_thresh`` (fractions in
    ``[0, 1]``). Legacy keys ``low_thr``/``high_thr`` carry **percentage**
    semantics (``0..100``) and are divided by 100 deterministically, with a
    migration log. Mixing canonical and legacy forms for the same threshold,
    out-of-range values, or ``low_thresh > h_thresh`` are explicit
    configuration errors (never silently swapped or clamped).

    Non-threshold parameters keep a documented fallback to defaults on invalid
    input, but the effective value is always returned so it can be journaled.

    Returns ``(params, error)`` where ``params`` is a dict of canonical
    effective parameters (or ``None``) and ``error`` is a message (or ``None``).
    """
    _log = log_callback if callable(log_callback) else (lambda k, **kw: None)
    input_params = sat_params_input or {}

    thresholds = {}
    for canonical_key, role, legacy_key in (
        ('low_thresh', 'low', 'low_thr'),
        ('h_thresh', 'high', 'high_thr'),
    ):
        canonical_val = input_params.get(canonical_key)
        legacy_val = input_params.get(legacy_key)
        has_canonical = canonical_val is not None
        has_legacy = legacy_val is not None

        if has_canonical and has_legacy:
            return None, (
                f"Configuration ambiguous: both canonical '{canonical_key}' and "
                f"legacy '{legacy_key}' provided for the {role} threshold."
            )
        if has_canonical:
            try:
                val = float(canonical_val)
            except (TypeError, ValueError):
                return None, f"Invalid {canonical_key} value: {canonical_val!r}"
            if not 0.0 <= val <= 1.0:
                return None, (
                    f"Invalid {canonical_key}={val}: must be a fraction in [0, 1]."
                )
            thresholds[role] = val
        elif has_legacy:
            try:
                val = float(legacy_val)
            except (TypeError, ValueError):
                return None, f"Invalid {legacy_key} value: {legacy_val!r}"
            if not 0.0 <= val <= 100.0:
                return None, (
                    f"Invalid {legacy_key}={val}: percentage must be in [0, 100]."
                )
            fraction = val / 100.0
            _log(
                "logic_trail_threshold_legacy_migration",
                legacy_key=legacy_key,
                legacy_value=val,
                canonical_key=canonical_key,
                canonical_value=fraction,
            )
            thresholds[role] = fraction
        else:
            thresholds[role] = TRAIL_PARAM_DEFAULTS[canonical_key]

    low = thresholds['low']
    high = thresholds['high']
    if low > high:
        return None, (
            f"Invalid thresholds: low_thresh={low} > h_thresh={high} "
            "(low must be <= high)."
        )

    params = {'low_thresh': low, 'h_thresh': high}
    for key in ('sigma', 'line_len', 'small_edge', 'line_gap'):
        default_val = TRAIL_PARAM_DEFAULTS[key]
        raw = input_params.get(key)
        current = default_val
        if raw is not None:
            try:
                if key == 'sigma':
                    current = float(raw)
                else:
                    current = int(raw)
                if key == 'sigma' and current <= 0:
                    raise ValueError('must be > 0')
                if key == 'line_len' and current <= 0:
                    raise ValueError('must be > 0')
                if key == 'small_edge' and current < 0:
                    raise ValueError('must be >= 0')
                if key == 'line_gap' and current <= 0:
                    raise ValueError('must be > 0')
            except (TypeError, ValueError):
                current = default_val
        params[key] = current

    return params, None


# --- RESTORED FUNCTION (rétro-compatible str/list/tuple) ---
def run_trail_detection(search_pattern, sat_params_input, status_callback=None, log_callback=None):
    """
    Exécute acstools.satdet.detsat pour détecter les traînées en utilisant un search_pattern ou une liste de fichiers.
    (Version rétro-compatible : accepte str, list, tuple)

    Sur une configuration de seuils invalide, retourne une erreur globale
    ``CONFIG_ERROR`` et n'appelle jamais acstools.
    """
    _status_callback = status_callback if callable(status_callback) else lambda k, **kw: print(f"TRAIL_STATUS: {k} {kw}")
    _log_callback = log_callback if callable(log_callback) else lambda k, **kw: print(f"TRAIL_LOG: {k} {kw}")

    # --- Vérifications Préalables ---
    if not SATDET_AVAILABLE or not SATDET_USES_SEARCHPATTERN: # Vérifier si compatible pattern
        err_msg = "Détection traînées non disponible ou incompatible avec les search patterns."
        _log_callback("logic_error_prefix", text=err_msg)
        return {}, {('FATAL_ERROR', 0): err_msg}

    # --- Nouvelle logique d’entrée rétro-compatible ---
    if isinstance(search_pattern, (list, tuple)):
        file_input = search_pattern
    elif isinstance(search_pattern, str):
        file_input = search_pattern
    else:
        err_msg = f"Type d'entrée invalide pour run_trail_detection: {type(search_pattern)}. Attendu str ou list/tuple."
        _log_callback("logic_error_prefix", text=err_msg)
        return {}, {('CONFIG_ERROR', 0): err_msg}

    if not SCIPY_AVAILABLE or not SKIMAGE_AVAILABLE:
         missing_deps = [dep for dep, avail in [("scipy", SCIPY_AVAILABLE), ("scikit-image", SKIMAGE_AVAILABLE)] if not avail]
         err_msg = f"Dépendances manquantes pour satdet: {', '.join(missing_deps)}"
         _log_callback("logic_error_prefix", text=err_msg); _status_callback("status_satdet_dep_error")
         return {}, {('DEPENDENCY_ERROR', 0): err_msg}

    # --- Résoudre et valider les paramètres canoniques ---
    params, cfg_error = resolve_trail_params(sat_params_input, _log_callback)
    if cfg_error is not None:
        _log_callback("logic_trail_config_error", text=cfg_error)
        _status_callback("status_satdet_error")
        return {}, {('CONFIG_ERROR', 0): cfg_error}

    # --- Paramètres fixes (inchangé) ---
    chips_to_use = [0]; n_processes = 1; verbose_det = False; plot_det = False

    # --- Exécution de satdet ---
    _status_callback("status_satdet_wait"); _log_callback("logic_satdet_params", **params, chips=chips_to_use)
    results = {}; errors = {}
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(action='ignore', message=r'.*is not a valid science extension.*', category=UserWarning)

            # --- Appel à satdet avec file_input (rétro-compatible str/list/tuple) ---
            # Déterminer le nom du premier argument attendu par detsat
            sig = inspect.signature(satdet.detsat)
            first_param_name = list(sig.parameters)[0]

            satdet_kwargs = {
                'chips': chips_to_use, 'n_processes': n_processes, 'sigma': params['sigma'],
                'low_thresh': params['low_thresh'], 'h_thresh': params['h_thresh'],
                'line_len': params['line_len'], 'small_edge': params['small_edge'],
                'line_gap': params['line_gap'], 'plot': plot_det, 'verbose': verbose_det
            }

            if isinstance(file_input, str):
                # Mode pattern unique
                satdet_kwargs[first_param_name] = file_input
                results, errors = satdet.detsat(**satdet_kwargs)
            else:
                # Mode liste : appeler satdet pour chaque fichier et fusionner les résultats
                results = {}
                errors = {}
                for single_file in file_input:
                    # A list/tuple contains literal file names, not glob
                    # patterns. Escape metacharacters such as ``[``/``*`` so
                    # acstools' internal glob expansion still opens the exact
                    # requested file.
                    satdet_kwargs[first_param_name] = glob.escape(os.fspath(single_file))
                    res, err = satdet.detsat(**satdet_kwargs)
                    results.update(res)
                    errors.update(err)
            # --- FIN RESTORED ---

        _status_callback("status_satdet_done")

        # Logguer les erreurs spécifiques
        if errors:
            _log_callback("logic_satdet_errors_title"); count = 0
            for key, msg in errors.items():
                if is_global_error_key(key):
                    _log_callback("logic_error_prefix", text=f"Erreur Satdet globale ({key}): {msg}"); count += 1
                    continue
                norm_key = normalize_detsat_key(key)
                if norm_key is None:
                    _log_callback("logic_error_prefix", text=f"Erreur Satdet clé inconnue ({key}): {msg}"); count += 1
                    continue
                fname, ext = norm_key
                if "is not a valid science extension" not in str(msg):
                    _log_callback("logic_satdet_errors_item", fname=os.path.basename(fname), ext=ext, msg=msg); count += 1
                else:
                    _log_callback("logic_error_prefix", text=f"Erreur Satdet non liée à un fichier ({key}): {msg}"); count += 1
            if count == 0: _log_callback("logic_satdet_errors_none")
        return results, errors

    except ImportError as imp_err: err_msg = f"Erreur d'importation interne lors de l'appel à satdet: {imp_err}."; _log_callback("logic_satdet_import_error", e=imp_err); _status_callback("status_satdet_dep_error"); return {}, {('IMPORT_ERROR', 0): err_msg}
    except Exception as e:
         err_msg = f"Erreur majeure lors de l'appel à acstools.satdet.detsat: {e}"; _log_callback("logic_satdet_major_error", e=e); print("\n--- Traceback Erreur Trail Module ---"); traceback.print_exc(); print("-----------------------------------\n"); _status_callback("status_satdet_error"); return {}, {('FATAL_ERROR', 0): str(e)}

# --- FIN DU FICHIER trail_module.py ---
