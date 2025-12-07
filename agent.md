# Mission – Keep FWHM/ECC implementation in ecc_module.py aligned with the PDF FWHM_Explanation.pdf

## Context

We have documented the new FWHM algorithm in `FWHM_Explanation.pdf` (4 stages):
1. Background estimation (sigma_clipped_stats)
2. Star detection (DAOStarFinder)
3. Star quality filtering (sharpness / roundness)
4. FWHM from second moments of the PSF footprint (per star), then median

The current `ecc_module.calculate_fwhm_ecc` already follows this method and
gives values close to PixInsight’s SubframeSelector on the test frame
`Light_M 31_20.0s_IRCUT_20251117-214019.fit`:

- Starcount ≈ 130–150 (more than PI, by design)
- FWHM ≈ 4.9 px (PI ≈ 5.8 px)
- Ecc ≈ 0.5–0.6

Starcount is intentionally more permissive; **the “magic” is in the FWHM
computation**, not in matching PI’s star count.

## Files to work on

- `ecc_module.py`
- `starcount_module.py` (only for shared detection helper)

## Goal

- Ensure `ecc_module.calculate_fwhm_ecc` strictly implements the
  PDF algorithm (4 stages) and stays stable.
- Ensure `starcount_module.calculate_starcount` uses **the same detection
  and shape filtering**, but only returns the number of detections.

## Requirements

### 1. Shared detection helper

In `ecc_module.py`, make sure there is a helper:

```python
DEFAULT_THRESHOLD_SIGMA = 5.0
DEFAULT_SHARPLO = 0.2
DEFAULT_SHARPHI = 1.0
DEFAULT_ROUNDLO = -0.6
DEFAULT_ROUNDHI = 0.6

def _detect_stars(
    data,
    fwhm,
    threshold_sigma=DEFAULT_THRESHOLD_SIGMA,
    sky_bg=None,
    sky_noise=None,
    *,
    sharplo=DEFAULT_SHARPLO,
    sharphi=DEFAULT_SHARPHI,
    roundlo=DEFAULT_ROUNDLO,
    roundhi=DEFAULT_ROUNDHI,
):
    """
    Stage 1 + 2 + 3 of the PDF:
      - background/noise via sigma_clipped_stats if needed
      - run DAOStarFinder(data - bg, threshold_sigma * noise)
      - apply shape filters:
          sharplo < sharpness < sharphi
          |roundness1| < |roundhi|
          |roundness2| < |roundhi|
    Return (bg, noise, sources_table_or_None).
    """
````

Implementation details:

* Use `sigma_clipped_stats(data, sigma=3.0, maxiters=5)` when `sky_bg` /
  `sky_noise` are None or invalid.
* If `noise <= 0` or everything is non-finite, return `(np.nan, np.nan, None)`.
* DAOStarFinder config:

  * `fwhm=fwhm`
  * `threshold=threshold_sigma * noise`
* Shape filters exactly as in the PDF.

### 2. Starcount module

In `starcount_module.py`:

* Import `_detect_stars` and `DEFAULT_THRESHOLD_SIGMA` from `ecc_module`.
* Implement:

```python
def calculate_starcount(
    data,
    fwhm=3.5,
    threshold_sigma=DEFAULT_THRESHOLD_SIGMA,
    *,
    sky_bg=None,
    sky_noise=None,
):
    """
    Return the number of detected stars using the same detection/shape
    filters as ecc_module.calculate_fwhm_ecc.
    This is intentionally more permissive than PixInsight.
    """
    try:
        _, _, tbl = _detect_stars(
            np.asarray(data),
            fwhm=fwhm,
            threshold_sigma=threshold_sigma,
            sky_bg=sky_bg,
            sky_noise=sky_noise,
        )
        return 0 if tbl is None else int(len(tbl))
    except Exception:
        return 0
```

* Do **not** add extra clipping or hard-coded limits in starcount.
  Starcount “being high” is acceptable.

### 3. FWHM/ECC (Stage 4 from PDF)

`calculate_fwhm_ecc` must implement exactly the 4th stage:

* Use `_detect_stars` for stages 1–3.
* If no stars → `(nan, nan, 0)`.

For each star:

1. Extract a small box (`box_radius` parameter) around (xcentroid, ycentroid).

2. Work on `cutout = data[y_min:y_max, x_min:x_max] - bg`.

3. Clip negatives: `cutout = np.clip(cutout, 0, None)`.

4. If total flux ≤ 0 → skip.

5. Compute flux-weighted centroid (x_mean, y_mean).

6. Compute second moments and covariance matrix.

7. Eigenvalues → `sigma_major²`, `sigma_minor²`.

8. Convert to FWHM:

   ```python
   fwhm_major = 2.3548 * sigma_major
   fwhm_minor = 2.3548 * sigma_minor
   fwhm_mean = 0.5 * (fwhm_major + fwhm_minor)
   ```

9. Eccentricity:

   ```python
   ecc = np.sqrt(1.0 - sigma_minor2 / sigma_major2)
   ```

Append valid `(fwhm_mean, ecc)` values to lists.

Final FWHM/ECC:

* If no valid values → `(nan, nan, 0)`.
* Otherwise:

  * `fwhm_med = median(fwhm_list)`
  * `ecc_med = median(ecc_list)`
  * `n = len(fwhm_list)`
* Return `(fwhm_med, ecc_med, n)`.

No extra percentile clipping is mandatory; the **median itself provides robustness**
as described in the PDF.

### 4. Public API

Keep the signatures:

```python
def calculate_starcount(data, fwhm=3.5, threshold_sigma=5.0, *, sky_bg=None, sky_noise=None) -> int
def calculate_fwhm_ecc(data, fwhm_guess=3.5, threshold_sigma=5.0, *, sky_bg=None, sky_noise=None, box_radius=4)
```

Do **not** change argument order or return types; do not touch callers.

---

## Tests (informal)

Use a REPL test:

```python
from astropy.io import fits
import starcount_module, ecc_module

path = "/mnt/stacking/test/Light_M 31_20.0s_IRCUT_20251117-214019.fit"
data = fits.open(path)[0].data

sc = starcount_module.calculate_starcount(data)
fwhm_px, ecc, n = ecc_module.calculate_fwhm_ecc(data)

print("Starcount:", sc)
print("FWHM:", fwhm_px)
print("Ecc:", ecc)
print("Stars used:", n)
```

Expected ballpark:

* Starcount: ~100–200 (more than PI, but not absurdly huge)
* FWHM: ~4.8–5.2 px
* Ecc: ~0.5–0.7
* Stars used: ≈ starcount

