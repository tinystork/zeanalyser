# Spike TRAIL-02A — satdet vs MRT (corpus synthétique)

- size=192 px, theta_step=1.0°, seed=20261002
- RSS method: resource.getrusage(RUSAGE_SELF).ru_maxrss (child peak, KiB); delta = child peak - import-only baseline
- baselines (import-only, KiB): satdet=170020, mrt=169656

## Tableau par cas

| case | backend | state | t(s) | detected | seg/sources | acc(2)/cand(1) | FP | angle_err |
|---|---|---|---|---|---|---|---|---|
| diag_strong | acstools.satdet | ok | 0.013 | O | 2 | - | TP | 0.0 |
| diag_strong | acstools.findsat_mrt | ok | 1.282 | O | 1 | 1/1 | TP | 0.0 |
| horiz_strong | acstools.satdet | ok | 0.012 | . | 0 | - | FN | - |
| horiz_strong | acstools.findsat_mrt | ok | 1.321 | O | 1 | 1/1 | TP | 0.0 |
| vert_strong | acstools.satdet | ok | 0.012 | . | 0 | - | FN | - |
| vert_strong | acstools.findsat_mrt | ok | 1.326 | O | 2 | 2/2 | TP | 1.5 |
| diag_weak | acstools.satdet | ok | 0.013 | . | 0 | - | FN | - |
| diag_weak | acstools.findsat_mrt | ok | 1.443 | O | 1 | 1/1 | TP | 0.0 |
| diag_short | acstools.satdet | ok | 0.012 | . | 0 | - | FN | - |
| diag_short | acstools.findsat_mrt | ok | 1.347 | . | 1 | 0/1 | FN | - |
| diag_partial | acstools.satdet | ok | 0.012 | . | 0 | - | FN | - |
| diag_partial | acstools.findsat_mrt | ok | 1.334 | . | 1 | 0/1 | FN | - |
| two_trails | acstools.satdet | ok | 0.014 | O | 2 | - | TP | - |
| two_trails | acstools.findsat_mrt | ok | 1.395 | O | 2 | 2/2 | TP | - |
| noise_stars | acstools.satdet | ok | 0.013 | . | 0 | - | TN | - |
| noise_stars | acstools.findsat_mrt | ok | 1.302 | . | 0 | 0/0 | TN | - |
| aligned_stars | acstools.satdet | ok | 0.012 | . | 0 | - | TN | - |
| aligned_stars | acstools.findsat_mrt | ok | 1.641 | . | 1 | 0/1 | TN | - |
| column_defect | acstools.satdet | ok | 0.015 | . | 0 | - | TN | - |
| column_defect | acstools.findsat_mrt | ok | 1.408 | O | 2 | 2/2 | FP | - |
| filament_gradient | acstools.satdet | ok | 0.011 | . | 0 | - | TN | - |
| filament_gradient | acstools.findsat_mrt | ok | 1.297 | . | 1 | 0/0 | TN | - |
| dense_field | acstools.satdet | ok | 0.022 | . | 0 | - | TN | - |
| dense_field | acstools.findsat_mrt | ok | 1.373 | O | 3 | 1/1 | FP | - |

## Synthèse synthétique (labels *synthetic*, pas produit)

### acstools.satdet
- évalués ok=12 erreur=0 timeout=0 (non évalués: positif=0 négatif=0)
- positives=7 négatifs=5
- TP=2 FP=0 FN=5 TN=5
- détection (positives)=0.286 FP rate (négatifs)=0.0
- temps: mean=0.0133s p50=0.012524799500170047s p95=0.01819090804992811s (n=12)

### acstools.findsat_mrt
- évalués ok=12 erreur=0 timeout=0 (non évalués: positif=0 négatif=0)
- positives=7 négatifs=5
- TP=5 FP=2 FN=2 TN=3
- détection (positives)=0.714 FP rate (négatifs)=0.4
- temps: mean=1.3724s p50=1.3403854944999694s p95=1.532303755149678s (n=12)
