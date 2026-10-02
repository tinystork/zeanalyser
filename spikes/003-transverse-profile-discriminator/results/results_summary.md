# Spike TRAIL-02C — profil transverse (discriminateur de forme)

- seeds: dev=20261005 blind=20261006
- config SHA-256: `30eae771ba70d0a744bb3dca6ac42fde16d08188249ec6693e22d01f7c59ad71`
- config (frozen): `{"aicc_delta_threshold": 4.0, "column_flat_top_ratio": 2.0, "column_softness_bounds": [0.01, 4.0], "column_width_bounds": [0.5, 20.0], "fit_max_nfev": 2000, "max_rss_frac": 0.1, "min_snr": 4.0, "pref_delta_threshold": 0.1, "ridge_sigma_bounds": [0.3, 10.0], "sample_half_width": 10.0, "sample_long_reduce": "median", "sample_offset_step": 0.25, "sample_order": 1}`

## Split `dev` — matrice ridge/column/ambiguous

- n=45 converged=45
- ridge recall=0.708 (ridge->column=4, ridge->ambiguous=3)
- column recall=0.9 (column->ridge=1, column->ambiguous=0)
- ambiguous: GT=11 pred=9 correct=6 promoted=5
- runtime mean=0.082s p50=0.0738s p95=0.11742739999999997s

| case | kind | GT | pred | corr | pref | snr | conv | sigma/width err |
|---|---|---|---|---|---|---|---|---|
| ridge_s0.6_c0.0 | ridge | ridge | ambiguous | False | -0.304 | 208.0 | True | 0.050 |
| ridge_s0.6_c0.25 | ridge | ridge | ridge | True | +0.260 | 32.0 | True | 0.136 |
| ridge_s0.6_c0.5 | ridge | ridge | column | False | -0.511 | 5.9 | True | 0.185 |
| ridge_s0.6_c0.75 | ridge | ridge | ridge | True | +0.444 | 76.4 | True | 0.131 |
| ridge_s0.8_c0.0 | ridge | ridge | ridge | True | +0.360 | 26.9 | True | 0.101 |
| ridge_s0.8_c0.25 | ridge | ridge | ridge | True | +0.028 | 11.9 | True | 0.091 |
| ridge_s0.8_c0.5 | ridge | ridge | ridge | True | +0.466 | 70.1 | True | 0.101 |
| ridge_s0.8_c0.75 | ridge | ridge | ambiguous | False | +0.010 | 27.8 | True | 0.097 |
| ridge_s1.2_c0.0 | ridge | ridge | ridge | True | +0.063 | 11.4 | True | 0.072 |
| ridge_s1.2_c0.25 | ridge | ridge | ridge | True | +0.660 | 57.3 | True | 0.059 |
| ridge_s1.2_c0.5 | ridge | ridge | ridge | True | +0.075 | 41.1 | True | 0.066 |
| ridge_s1.2_c0.75 | ridge | ridge | ridge | True | +0.221 | 11.2 | True | 0.041 |
| ridge_s1.5_c0.0 | ridge | ridge | ridge | True | +0.738 | 82.5 | True | 0.046 |
| ridge_s1.5_c0.25 | ridge | ridge | ridge | True | +0.183 | 37.6 | True | 0.051 |
| ridge_s1.5_c0.5 | ridge | ridge | ridge | True | +0.115 | 8.2 | True | 0.011 |
| ridge_s1.5_c0.75 | ridge | ridge | ridge | True | +0.133 | 83.9 | True | 0.050 |
| ridge_s2.5_c0.0 | ridge | ridge | ridge | True | +0.245 | 28.0 | True | 0.039 |
| ridge_s2.5_c0.25 | ridge | ridge | column | False | -0.041 | 10.6 | True | 0.107 |
| ridge_s2.5_c0.5 | ridge | ridge | ridge | True | +0.208 | 70.0 | True | 0.037 |
| ridge_s2.5_c0.75 | ridge | ridge | ridge | True | +0.380 | 26.8 | True | 0.036 |
| ridge_s3.5_c0.0 | ridge | ridge | ambiguous | False | -0.003 | 8.4 | True | 0.312 |
| ridge_s3.5_c0.25 | ridge | ridge | column | False | -0.412 | 39.7 | True | 0.555 |
| ridge_s3.5_c0.5 | ridge | ridge | ridge | True | +0.023 | 28.5 | True | 0.395 |
| ridge_s3.5_c0.75 | ridge | ridge | column | False | -0.295 | 8.8 | True | 0.321 |
| col_w1_b0.0 | column | column | ridge | False | +0.104 | 85.8 | True | 0.149 |
| col_w1_b0.5 | column | ambiguous | ambiguous | True | -0.241 | 63.1 | True | 0.500 |
| col_w1_b1.0 | column | ambiguous | ridge | False | +0.018 | 5.9 | True | 1.410 |
| col_w1_b2.0 | column | ambiguous | ridge | False | +0.169 | 15.8 | True | 3.130 |
| col_w2_b0.0 | column | column | column | True | -0.886 | 36.6 | True | 0.983 |
| col_w2_b0.5 | column | column | column | True | -0.551 | 7.1 | True | 0.035 |
| col_w2_b1.0 | column | ambiguous | ridge | False | +0.039 | 56.7 | True | 0.405 |
| col_w2_b2.0 | column | ambiguous | ridge | False | +0.194 | 14.3 | True | 2.202 |
| col_w4_b0.0 | column | column | column | True | -0.943 | 8.7 | True | 0.986 |
| col_w4_b0.5 | column | column | column | True | -0.940 | 77.6 | True | 0.009 |
| col_w4_b1.0 | column | column | column | True | -0.616 | 30.9 | True | 0.049 |
| col_w4_b2.0 | column | ambiguous | ambiguous | True | +0.000 | 5.7 | True | 0.875 |
| col_w6_b0.0 | column | column | column | True | -0.974 | 82.5 | True | 0.999 |
| col_w6_b0.5 | column | column | column | True | -0.977 | 36.6 | True | 0.002 |
| col_w6_b1.0 | column | column | column | True | -0.838 | 7.8 | True | 0.038 |
| col_w6_b2.0 | column | column | column | True | -0.424 | 61.4 | True | 0.017 |
| no_structure | no_structure | ambiguous | ambiguous | True | +0.000 | 0.2 | True | - |
| double_ridge | double_ridge | ambiguous | column | False | -0.860 | 51.0 | True | - |
| aligned_stars | aligned_stars | ambiguous | ambiguous | True | +0.000 | 1.5 | True | - |
| gradient | gradient | ambiguous | ambiguous | True | +0.000 | 0.1 | True | - |
| asymmetric | asymmetric | ambiguous | ambiguous | True | -0.028 | 43.1 | True | - |

## Split `blind` — matrice ridge/column/ambiguous

- n=26 converged=26
- ridge recall=0.667 (ridge->column=3, ridge->ambiguous=1)
- column recall=1.0 (column->ridge=0, column->ambiguous=0)
- ambiguous: GT=8 pred=4 correct=3 promoted=5
- runtime mean=0.0855s p50=0.076743s p95=0.1388885s

| case | kind | GT | pred | corr | pref | snr | conv | sigma/width err |
|---|---|---|---|---|---|---|---|---|
| ridge_s0.7_c0.125 | ridge | ridge | ridge | True | +0.436 | 34.1 | True | 0.119 |
| ridge_s0.7_c0.375 | ridge | ridge | column | False | -0.204 | 9.4 | True | 0.135 |
| ridge_s0.7_c0.625 | ridge | ridge | ridge | True | +0.542 | 53.9 | True | 0.116 |
| ridge_s1.0_c0.125 | ridge | ridge | ridge | True | +0.112 | 58.5 | True | 0.084 |
| ridge_s1.0_c0.375 | ridge | ridge | ridge | True | +0.532 | 36.1 | True | 0.076 |
| ridge_s1.0_c0.625 | ridge | ridge | ambiguous | False | -0.004 | 12.1 | True | 0.104 |
| ridge_s1.8_c0.125 | ridge | ridge | ridge | True | +0.242 | 13.0 | True | 0.010 |
| ridge_s1.8_c0.375 | ridge | ridge | ridge | True | +0.351 | 58.3 | True | 0.042 |
| ridge_s1.8_c0.625 | ridge | ridge | ridge | True | +0.485 | 36.5 | True | 0.022 |
| ridge_s3.0_c0.125 | ridge | ridge | column | False | -0.342 | 31.3 | True | 0.210 |
| ridge_s3.0_c0.375 | ridge | ridge | ridge | True | +0.189 | 11.1 | True | 0.136 |
| ridge_s3.0_c0.625 | ridge | ridge | column | False | -0.195 | 47.9 | True | 0.217 |
| col_w1.5_b0.25 | column | column | column | True | -0.672 | 35.5 | True | 0.466 |
| col_w1.5_b0.75 | column | ambiguous | column | False | -0.089 | 9.7 | True | 0.655 |
| col_w1.5_b1.5 | column | ambiguous | ridge | False | +0.149 | 29.4 | True | 1.736 |
| col_w3.0_b0.25 | column | column | column | True | -0.850 | 8.3 | True | 0.022 |
| col_w3.0_b0.75 | column | column | column | True | -0.844 | 65.7 | True | 0.972 |
| col_w3.0_b1.5 | column | ambiguous | ridge | False | +0.185 | 28.0 | True | 0.587 |
| col_w5.0_b0.25 | column | column | column | True | -0.957 | 82.3 | True | 0.005 |
| col_w5.0_b0.75 | column | column | column | True | -0.962 | 26.7 | True | 0.976 |
| col_w5.0_b1.5 | column | column | column | True | -0.205 | 9.3 | True | 0.063 |
| no_structure | no_structure | ambiguous | ambiguous | True | +0.000 | 0.1 | True | - |
| double_ridge | double_ridge | ambiguous | column | False | -0.957 | 45.5 | True | - |
| aligned_stars | aligned_stars | ambiguous | ambiguous | True | +0.000 | 1.1 | True | - |
| gradient | gradient | ambiguous | ambiguous | True | +0.000 | 0.1 | True | - |
| asymmetric | asymmetric | ambiguous | column | False | -0.033 | 33.8 | True | - |
