"""FWHM/ECC eigenvalue and DAOStarFinder parameter tests (BASE-02).

Covers the eigvalsh vs eigvals equivalence, degenerate/non-finite star
rejection, absence of ComplexWarning without any ``ignore`` filter, and the
modern/legacy DAOStarFinder parameter forms with exact kwargs.
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from zeanalyser import ecc_module


def gaussian_field(
    seed: int = 7,
    shape: tuple[int, int] = (160, 160),
    sigma: float = 1.5,
    amplitude: float = 100.0,
    noise: float = 1.0,
    n_stars: int = 9,
    border: int = 20,
):
    rng = np.random.default_rng(seed)
    img = rng.normal(0.0, noise, shape)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    side = int(np.ceil(np.sqrt(n_stars)))
    step_y = (shape[0] - 2 * border) // max(side - 1, 1)
    step_x = (shape[1] - 2 * border) // max(side - 1, 1)
    for i in range(n_stars):
        cy = border + (i // side) * step_y
        cx = border + (i % side) * step_x
        img = img + amplitude * np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma)
        )
    return img


# --- eigenvalue equivalence -------------------------------------------------

def test_eigvalsh_equals_eigvals_real_part_for_symmetric_covariance():
    covs = [
        np.array([[2.0, 0.0], [0.0, 2.0]]),
        np.array([[2.2, 0.001], [0.001, 2.19]]),
        np.array([[1.5, 0.3], [0.3, 2.5]]),
        np.array([[4.0, -0.7], [-0.7, 1.1]]),
    ]
    for cov in covs:
        general = np.sort(np.real(np.linalg.eigvals(cov)))
        hermitian = np.linalg.eigvalsh(cov)
        assert np.allclose(general, hermitian)


def test_second_moments_eigen_circular_gaussian():
    # A perfectly circular star: equal variances, zero covariance.
    cov = np.array([[2.25, 0.0], [0.0, 2.25]])
    major, minor = ecc_module._second_moments_eigen(cov)
    assert major == pytest.approx(2.25)
    assert minor == pytest.approx(2.25)


def test_second_moments_eigen_rejects_non_finite():
    assert ecc_module._second_moments_eigen(np.array([[np.nan, 0.0], [0.0, 1.0]])) is None
    assert ecc_module._second_moments_eigen(np.array([[np.inf, 0.0], [0.0, 1.0]])) is None


def test_second_moments_eigen_rejects_non_2x2():
    assert ecc_module._second_moments_eigen(np.array([[1.0]])) is None
    assert ecc_module._second_moments_eigen(np.zeros((3, 3))) is None


def test_second_moments_eigen_rejects_zero_major():
    assert ecc_module._second_moments_eigen(np.array([[0.0, 0.0], [0.0, 0.0]])) is None


def test_second_moments_eigen_rejects_negative_definite():
    assert ecc_module._second_moments_eigen(np.array([[-1.0, 0.0], [0.0, -1.0]])) is None


def test_second_moments_eigen_clips_negligible_negative_minor():
    # Negligible negative rounding on the minor variance is clipped to zero,
    # producing a valid (line-like) star rather than a failure.
    cov = np.array([[4.0, 0.0], [0.0, -1e-15]])
    result = ecc_module._second_moments_eigen(cov)
    assert result is not None
    major, minor = result
    assert major == pytest.approx(4.0)
    assert minor == 0.0


def test_second_moments_eigen_rejects_large_negative_minor():
    # A genuinely indefinite covariance is rejected.
    cov = np.array([[4.0, 0.0], [0.0, -1.0]])
    assert ecc_module._second_moments_eigen(cov) is None


def test_second_moments_eigen_elongated_star_is_valid():
    # A diagonal covariance with distinct variances is an elongated (elliptical)
    # but perfectly physical star: eigvalsh returns ascending eigenvalues, so the
    # minor variance is always <= the major variance.
    major, minor = ecc_module._second_moments_eigen(np.array([[1.0, 0.0], [0.0, 10.0]]))
    assert major == pytest.approx(10.0)
    assert minor == pytest.approx(1.0)


def test_no_complex_warning_on_measurement_without_ignore_filter():
    # The FWHM/ECC measurement must not emit ComplexWarning, and no global
    # ``ignore`` filter is applied anywhere in the measurement path.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        outcome = ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())

    assert outcome["outcome"] == "ok"
    complex_warnings = [
        w for w in caught
        if "ComplexWarning" in w.category.__name__ or "ComplexWarning" in str(w.message)
    ]
    assert complex_warnings == []


def test_historical_fwhm_tolerance_preserved():
    outcome = ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())
    assert outcome["outcome"] == "ok"
    # Documented historical relationship: FWHM = 2.3548 * sigma for a circular
    # Gaussian with sigma = 1.5 px (same tolerance as the legacy tests).
    assert outcome["fwhm"] == pytest.approx(2.3548 * 1.5, rel=0.03)
    assert 0.0 <= outcome["ecc"] <= 1.0


# --- DAOStarFinder parameter forms -----------------------------------------

class _FakeDAOStarFinder:
    """Captures the constructor kwargs for deterministic assertions."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeDAOStarFinder.instances.append(self)

    def __call__(self, _data):
        return None


def test_modern_path_uses_range_parameters(monkeypatch):
    _FakeDAOStarFinder.instances = []
    monkeypatch.setattr(ecc_module, "DAOStarFinder", _FakeDAOStarFinder)
    monkeypatch.setattr(ecc_module, "_HAS_SHARPNESS_RANGE", True)
    monkeypatch.setattr(ecc_module, "_HAS_ROUNDNESS_RANGE", True)

    finder = ecc_module._make_star_finder(
        fwhm=3.5,
        threshold_sigma=5.0,
        noise=2.0,
        sharplo=ecc_module.DEFAULT_SHARPLO,
        sharphi=ecc_module.DEFAULT_SHARPHI,
        roundlo=ecc_module.DEFAULT_ROUNDLO,
        roundhi=ecc_module.DEFAULT_ROUNDHI,
    )

    assert isinstance(finder, _FakeDAOStarFinder)
    kwargs = finder.kwargs
    assert "sharpness_range" in kwargs
    assert "roundness_range" in kwargs
    assert kwargs["sharpness_range"] == (ecc_module.DEFAULT_SHARPLO, ecc_module.DEFAULT_SHARPHI)
    assert kwargs["roundness_range"] == (ecc_module.DEFAULT_ROUNDLO, ecc_module.DEFAULT_ROUNDHI)
    assert kwargs["fwhm"] == 3.5
    assert kwargs["threshold"] == 5.0 * 2.0
    # deprecated parameters must be absent
    for deprecated in ("sharplo", "sharphi", "roundlo", "roundhi"):
        assert deprecated not in kwargs


def test_legacy_path_uses_deprecated_parameters(monkeypatch):
    _FakeDAOStarFinder.instances = []
    monkeypatch.setattr(ecc_module, "DAOStarFinder", _FakeDAOStarFinder)
    monkeypatch.setattr(ecc_module, "_HAS_SHARPNESS_RANGE", False)
    monkeypatch.setattr(ecc_module, "_HAS_ROUNDNESS_RANGE", False)

    finder = ecc_module._make_star_finder(
        fwhm=3.5,
        threshold_sigma=5.0,
        noise=2.0,
        sharplo=ecc_module.DEFAULT_SHARPLO,
        sharphi=ecc_module.DEFAULT_SHARPHI,
        roundlo=ecc_module.DEFAULT_ROUNDLO,
        roundhi=ecc_module.DEFAULT_ROUNDHI,
    )

    kwargs = finder.kwargs
    assert kwargs["sharplo"] == ecc_module.DEFAULT_SHARPLO
    assert kwargs["sharphi"] == ecc_module.DEFAULT_SHARPHI
    assert kwargs["roundlo"] == ecc_module.DEFAULT_ROUNDLO
    assert kwargs["roundhi"] == ecc_module.DEFAULT_ROUNDHI
    # new parameters must be absent
    assert "sharpness_range" not in kwargs
    assert "roundness_range" not in kwargs


def test_default_constants_unchanged():
    assert ecc_module.DEFAULT_SHARPLO == 0.2
    assert ecc_module.DEFAULT_SHARPHI == 1.0
    assert ecc_module.DEFAULT_ROUNDLO == -0.6
    assert ecc_module.DEFAULT_ROUNDHI == 0.6


def test_flags_reflect_installed_signature():
    # The import-time detection flags must faithfully reflect the installed
    # DAOStarFinder signature, whatever the Photutils version. There is no
    # hard assumption that range parameters are present: an older Photutils
    # without them must be detected as such (and handled by the legacy path).
    import inspect
    from photutils.detection import DAOStarFinder

    params = inspect.signature(DAOStarFinder.__init__).parameters
    assert ecc_module._HAS_SHARPNESS_RANGE == ("sharpness_range" in params)
    assert ecc_module._HAS_ROUNDNESS_RANGE == ("roundness_range" in params)


def test_no_targeted_deprecations_on_current_photutils():
    # Only meaningful when the installed Photutils supports the range
    # parameters (the modern path). In that case the modern detection path must
    # not use the deprecated sharplo/sharphi/roundlo/roundhi parameters, so a
    # real detection run emits none of the targeted deprecation warnings. When
    # the installed version is too old to expose the range parameters, this test
    # is skipped (the legacy fallback is covered by the dedicated legacy tests).
    if not (ecc_module._HAS_SHARPNESS_RANGE and ecc_module._HAS_ROUNDNESS_RANGE):
        pytest.skip("installed Photutils predates sharpness_range/roundness_range")

    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ecc_module.calculate_fwhm_ecc_outcome(gaussian_field())

    deprecations = [
        w for w in caught
        if "sharplo" in str(w.message) or "sharphi" in str(w.message)
        or "roundlo" in str(w.message) or "roundhi" in str(w.message)
    ]
    assert deprecations == []
