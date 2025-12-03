"""analysis_schema.py

Small helper that declares the expected structure/keys of an analysis result
row as produced by analyse_logic.perform_analysis. This will be used by the
Qt model (Phase 3) to present columns in a QTableView.

Keeping these keys here makes it explicit and easy to test and evolve.
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
