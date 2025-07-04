import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.detection import DAOStarFinder


def calculate_fwhm_ecc(data, fwhm_guess=3.5, threshold_sigma=5.):
    """Calculate median FWHM and eccentricity of stars in ``data``.

    Parameters
    ----------
    data : 2-D numpy array
        Image data.
    fwhm_guess : float
        Initial FWHM guess for DAOStarFinder.
    threshold_sigma : float
        Detection threshold in sigma units.

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
        mean, median, std = sigma_clipped_stats(data, sigma=3.0)
        finder = DAOStarFinder(fwhm=fwhm_guess, threshold=threshold_sigma * std)
        tbl = finder(data - median)
        if tbl is None or len(tbl) == 0:
            return np.nan, np.nan, 0

        a = tbl['a']
        b = tbl['b']
        if 'fwhm' in tbl.colnames:
            fwhm_vals = tbl['fwhm']
        else:
            fwhm_vals = 0.5 * (a + b)

        fwhm_med = np.nanmedian(fwhm_vals) if len(fwhm_vals) > 0 else np.nan
        ecc_vals = np.sqrt(1.0 - (b / a) ** 2)
        ecc_med = np.nanmedian(ecc_vals) if len(ecc_vals) > 0 else np.nan
        return float(fwhm_med), float(ecc_med), int(len(tbl))
    except Exception:
        return np.nan, np.nan, 0
