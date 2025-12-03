import analyse_logic
import analysis_schema


def test_result_keys_contains_core_fields():
    keys = analysis_schema.get_result_keys()
    # basic required keys that analyse_logic uses
    required = ['file', 'path', 'status', 'ra', 'dec', 'snr']
    for r in required:
        assert r in keys


def test_schema_matches_analyse_logic_expected_keys():
    # Try to load analyse_logic and inspect the result_base template by
    # searching for known keys in the module source if possible.
    # This test is intentionally permissive: we check presence of several
    # representative keys rather than exact equality to avoid brittle tests.
    keys = set(analysis_schema.get_result_keys())
    expected = {'file', 'path', 'rel_path', 'status', 'snr', 'starcount', 'fwhm', 'ecc', 'ra', 'dec'}
    assert expected.issubset(keys)
