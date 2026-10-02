# Spike TRAIL-02B — Hough adaptatif (corpus synthétique)

- size=256 px, seeds: dev=20261002, observed_holdout=20261003, blind=20261004
- RSS method: resource.getrusage(RUSAGE_SELF).ru_maxrss (child peak, KiB); delta = child peak - import-only baseline
- baselines (import-only, KiB): dev=67944, observed_holdout=68068, blind=68216

## Split `dev` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| diag_strong | ok | 1.351 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.87 |
| horiz_strong | ok | 1.335 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| vert_strong | ok | 1.329 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| diag_weak | ok | 1.331 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.70 |
| diag_short | ok | 1.351 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.83 |
| diag_partial | ok | 1.335 | 1 | 0 | FN | 0/1 | - | - | - |  |
| two_trails | ok | 1.649 | 2 | 2 | TP | 2/2 | 0.0 | 0.0 | 1.4 | 0.87 |
| noise_stars | ok | 1.298 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars | ok | 1.316 | 0 | 0 | TN | - | - | - | - |  |
| column_defect | ok | 1.343 | 1 | 0 | TN | - | - | - | - |  |
| filament_gradient | ok | 1.312 | 0 | 0 | TN | - | - | - | - |  |
| dense_field | ok | 1.282 | 0 | 0 | TN | - | - | - | - |  |

### Synthèse `dev` (labels *synthetic*, pas produit)
- ok=12 erreur=0 timeout=0
- positives=7 négatifs=5
- TP=6 FP=0 FN=1 TN=5
- détection (positives)=0.857 FP rate (négatifs)=0.0
- FP par classe=[]  FN par classe=['diag_partial']
- traces physiques: matched=7/8 (taux=0.875), extras sur positifs=0, multi-traces cohérentes=1/1
- erreur angle moyenne=0.0°
- temps: mean=1.3526s p50=1.3326500000000001s p95=1.4852849999999997s (n=12)

## Split `observed_holdout` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| h_axis | ok | 1.328 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| v_axis | ok | 1.328 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| diag_weak_b | ok | 1.374 | 1 | 0 | FN | 0/1 | - | - | - |  |
| diag_short_b | ok | 1.358 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.81 |
| diag_partial_b | ok | 1.313 | 1 | 1 | TP | 1/1 | 0.2 | 0.8 | 1.2 | 0.84 |
| two_trails_b | ok | 1.296 | 2 | 2 | TP | 2/2 | 0.0 | 0.1 | 1.6 | 0.89 |
| diag_wide_b | ok | 1.355 | 2 | 1 | TP | 1/1 | 0.0 | 1.4 | 2.0 | 0.88 |
| noise_stars_b | ok | 1.561 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars_b | ok | 1.343 | 0 | 0 | TN | - | - | - | - |  |
| column_defect_b | ok | 1.402 | 1 | 0 | TN | - | - | - | - |  |
| column_defect_1px | ok | 1.342 | 1 | 0 | TN | - | - | - | - |  |
| filament_gradient_b | ok | 1.398 | 0 | 0 | TN | - | - | - | - |  |
| dense_field_b | ok | 1.228 | 0 | 0 | TN | - | - | - | - |  |

### Synthèse `observed_holdout` (labels *synthetic*, pas produit)
- ok=13 erreur=0 timeout=0
- positives=7 négatifs=6
- TP=6 FP=0 FN=1 TN=6
- détection (positives)=0.857 FP rate (négatifs)=0.0
- FP par classe=[]  FN par classe=['diag_weak_b']
- traces physiques: matched=7/8 (taux=0.875), extras sur positifs=0, multi-traces cohérentes=1/1
- erreur angle moyenne=0.04°
- temps: mean=1.3559s p50=1.3427s p95=1.4653199999999997s (n=13)

## Split `blind` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| near_wrap_179 | ok | 1.317 | 1 | 1 | TP | 1/1 | 0.1 | 0.8 | 1.3 | 0.87 |
| offaxis_91 | ok | 1.340 | 1 | 0 | FN | 0/1 | - | - | - |  |
| weak_73 | ok | 1.365 | 1 | 1 | TP | 1/1 | 0.0 | 0.1 | 1.6 | 0.72 |
| short_67 | ok | 1.329 | 1 | 1 | TP | 1/1 | 0.2 | 1.5 | 7.1 | 0.82 |
| partial_112 | ok | 1.343 | 1 | 1 | TP | 1/1 | 0.0 | 0.2 | 9.9 | 0.84 |
| two_mixed | ok | 1.317 | 2 | 1 | TP | 1/2 | 0.0 | 0.9 | 1.7 | 0.88 |
| thin_38 | ok | 1.421 | 1 | 0 | FN | 0/1 | - | - | - |  |
| wide_141 | ok | 1.325 | 3 | 1 | TP | 1/1 | 0.2 | 0.4 | 2.5 | 0.83 |
| noise_stars_c | ok | 1.451 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars_67 | ok | 1.351 | 0 | 0 | TN | - | - | - | - |  |
| hard_column_1px | ok | 1.396 | 1 | 0 | TN | - | - | - | - |  |
| soft_column_4px | ok | 2.845 | 89 | 1 | FP | - | - | - | - | 0.87 |
| hard_row_2px | ok | 1.315 | 1 | 0 | TN | - | - | - | - |  |
| tracking_dashes | ok | 1.376 | 1 | 0 | TN | - | - | - | - |  |
| curved_filament | ok | 1.306 | 0 | 0 | TN | - | - | - | - |  |
| dense_field_c | ok | 1.282 | 1 | 0 | TN | - | - | - | - |  |
| gradient_c | ok | 1.333 | 0 | 0 | TN | - | - | - | - |  |

### Synthèse `blind` (labels *synthetic*, pas produit)
- ok=17 erreur=0 timeout=0
- positives=8 négatifs=9
- TP=6 FP=1 FN=2 TN=8
- détection (positives)=0.75 FP rate (négatifs)=0.111
- FP par classe=['soft_column_4px']  FN par classe=['offaxis_91', 'thin_38']
- traces physiques: matched=6/9 (taux=0.667), extras sur positifs=0, multi-traces cohérentes=0/1
- erreur angle moyenne=0.08°
- temps: mean=1.4361s p50=1.34s p95=1.730199999999999s (n=17)

## Comparaison grossière (satdet/MRT publics 001, observed_holdout)

*In-process, runtime seul, non isolé RSS — non comparable aux lignes custom isolées.*

- **satdet**: détection=0.286 FP rate=0.0 FP=[] FN=['diag_partial_b', 'diag_short_b', 'h_axis', 'two_trails_b', 'v_axis']
- **mrt**: détection=1.0 FP rate=0.5 FP=['aligned_stars_b', 'column_defect_1px', 'column_defect_b'] FN=[]
