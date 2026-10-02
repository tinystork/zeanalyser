# Spike TRAIL-02B — Hough adaptatif (corpus synthétique)

- size=192 px, seeds: dev=20261002, observed_holdout=20261003, blind=20261004
- RSS method: resource.getrusage(RUSAGE_SELF).ru_maxrss (child peak, KiB); delta = child peak - import-only baseline
- baselines (import-only, KiB): dev=68104, observed_holdout=67968, blind=68120

## Split `dev` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| diag_strong | ok | 0.527 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.87 |
| horiz_strong | ok | 0.438 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| vert_strong | ok | 0.485 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| diag_weak | ok | 0.451 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.69 |
| diag_short | ok | 0.459 | 1 | 0 | FN | 0/1 | - | - | - |  |
| diag_partial | ok | 0.473 | 1 | 1 | TP | 1/1 | 0.2 | 0.8 | 1.7 | 0.86 |
| two_trails | ok | 0.500 | 2 | 2 | TP | 2/2 | 0.0 | 0.0 | 1.4 | 0.87 |
| noise_stars | ok | 0.431 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars | ok | 0.477 | 1 | 0 | TN | - | - | - | - |  |
| column_defect | ok | 0.459 | 1 | 0 | TN | - | - | - | - |  |
| filament_gradient | ok | 0.429 | 0 | 0 | TN | - | - | - | - |  |
| dense_field | ok | 0.468 | 6 | 0 | TN | - | - | - | - |  |

### Synthèse `dev` (labels *synthetic*, pas produit)
- ok=12 erreur=0 timeout=0
- positives=7 négatifs=5
- TP=6 FP=0 FN=1 TN=5
- détection (positives)=0.857 FP rate (négatifs)=0.0
- FP par classe=[]  FN par classe=['diag_short']
- traces physiques: matched=7/8 (taux=0.875), extras sur positifs=0, multi-traces cohérentes=1/1
- erreur angle moyenne=0.04°
- temps: mean=0.4664s p50=0.4636s p95=0.512205s (n=12)

## Split `observed_holdout` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| h_axis | ok | 0.438 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| v_axis | ok | 0.460 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.0 | 0.87 |
| diag_weak_b | ok | 0.461 | 1 | 1 | TP | 1/1 | 0.1 | 0.1 | 1.1 | 0.69 |
| diag_short_b | ok | 0.441 | 1 | 0 | FN | 0/1 | - | - | - |  |
| diag_partial_b | ok | 0.460 | 1 | 0 | FN | 0/1 | - | - | - |  |
| two_trails_b | ok | 0.468 | 2 | 2 | TP | 2/2 | 0.2 | 1.2 | 1.8 | 0.89 |
| diag_wide_b | ok | 0.433 | 1 | 1 | TP | 1/1 | 0.0 | 0.0 | 1.4 | 0.86 |
| noise_stars_b | ok | 0.466 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars_b | ok | 0.440 | 1 | 0 | TN | - | - | - | - |  |
| column_defect_b | ok | 0.461 | 1 | 0 | TN | - | - | - | - |  |
| column_defect_1px | ok | 0.451 | 1 | 0 | TN | - | - | - | - |  |
| filament_gradient_b | ok | 0.571 | 0 | 0 | TN | - | - | - | - |  |
| dense_field_b | ok | 0.494 | 8 | 0 | TN | - | - | - | - |  |

### Synthèse `observed_holdout` (labels *synthetic*, pas produit)
- ok=13 erreur=0 timeout=0
- positives=7 négatifs=6
- TP=5 FP=0 FN=2 TN=6
- détection (positives)=0.714 FP rate (négatifs)=0.0
- FP par classe=[]  FN par classe=['diag_partial_b', 'diag_short_b']
- traces physiques: matched=6/8 (taux=0.75), extras sur positifs=0, multi-traces cohérentes=1/1
- erreur angle moyenne=0.06°
- temps: mean=0.4648s p50=0.4595s p95=0.5249799999999999s (n=13)

## Split `blind` — tableau par cas

| case | state | t(s) | trails | acc | verdict | matched/GT | angle_err | offset_px | endpt_px | score |
|---|---|---|---|---|---|---|---|---|---|---|
| near_wrap_179 | ok | 0.437 | 1 | 1 | TP | 1/1 | 0.0 | 0.8 | 1.3 | 0.87 |
| offaxis_91 | ok | 0.455 | 1 | 1 | TP | 1/1 | 0.0 | 0.8 | 1.3 | 0.88 |
| weak_73 | ok | 0.441 | 1 | 1 | TP | 1/1 | 0.0 | 0.2 | 1.7 | 0.65 |
| short_67 | ok | 0.458 | 1 | 1 | TP | 1/1 | 0.6 | 0.5 | 1.9 | 0.82 |
| partial_112 | ok | 0.447 | 1 | 1 | TP | 1/1 | 0.0 | 1.1 | 5.9 | 0.84 |
| two_mixed | ok | 0.455 | 2 | 2 | TP | 2/2 | 0.1 | 0.7 | 1.9 | 0.88 |
| thin_38 | ok | 0.468 | 1 | 0 | FN | 0/1 | - | - | - |  |
| wide_141 | ok | 0.454 | 2 | 1 | TP | 1/1 | 0.6 | 0.7 | 2.2 | 0.83 |
| noise_stars_c | ok | 0.436 | 0 | 0 | TN | - | - | - | - |  |
| aligned_stars_67 | ok | 0.484 | 0 | 0 | TN | - | - | - | - |  |
| hard_column_1px | ok | 0.459 | 1 | 0 | TN | - | - | - | - |  |
| soft_column_4px | ok | 1.328 | 81 | 0 | TN | - | - | - | - |  |
| hard_row_2px | ok | 0.455 | 1 | 0 | TN | - | - | - | - |  |
| tracking_dashes | ok | 0.429 | 0 | 0 | TN | - | - | - | - |  |
| curved_filament | ok | 0.432 | 0 | 0 | TN | - | - | - | - |  |
| dense_field_c | ok | 0.592 | 21 | 0 | TN | - | - | - | - |  |
| gradient_c | ok | 0.435 | 0 | 0 | TN | - | - | - | - |  |

### Synthèse `blind` (labels *synthetic*, pas produit)
- ok=17 erreur=0 timeout=0
- positives=8 négatifs=9
- TP=7 FP=0 FN=1 TN=9
- détection (positives)=0.875 FP rate (négatifs)=0.0
- FP par classe=[]  FN par classe=['thin_38']
- traces physiques: matched=8/9 (taux=0.889), extras sur positifs=0, multi-traces cohérentes=1/1
- erreur angle moyenne=0.19°
- temps: mean=0.5097s p50=0.4545s p95=0.7394799999999995s (n=17)

## Comparaison grossière (satdet/MRT publics 001, observed_holdout)

*In-process, runtime seul, non isolé RSS — non comparable aux lignes custom isolées.*

- **satdet**: détection=0.0 FP rate=0.0 FP=[] FN=['diag_partial_b', 'diag_short_b', 'diag_weak_b', 'diag_wide_b', 'h_axis', 'two_trails_b', 'v_axis']
- **mrt**: détection=0.857 FP rate=0.5 FP=['aligned_stars_b', 'column_defect_1px', 'column_defect_b'] FN=['diag_short_b']
