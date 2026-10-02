# Spike TRAIL-02A — satdet vs MRT (corpus synthétique)

- size=256 px, theta_step=0.5°, seed=20261002
- RSS method: resource.getrusage(RUSAGE_SELF).ru_maxrss (child peak, KiB); delta = child peak - import-only baseline
- baselines (import-only, KiB): satdet=172140, mrt=172140

## Tableau par cas

| case | backend | state | t(s) | detected | seg/sources | acc(2)/cand(1) | FP | angle_err |
|---|---|---|---|---|---|---|---|---|
| diag_strong | acstools.satdet | ok | 0.020 | O | 2 | - | TP | 0.0 |
| diag_strong | acstools.findsat_mrt | ok | 3.739 | O | 1 | 1/1 | TP | 0.0 |
| vert_strong | acstools.satdet | ok | 0.017 | . | 0 | - | FN | - |
| vert_strong | acstools.findsat_mrt | ok | 3.850 | O | 2 | 2/2 | TP | 1.0 |
| dense_field | acstools.satdet | ok | 0.022 | . | 0 | - | TN | - |
| dense_field | acstools.findsat_mrt | ok | 3.812 | . | 2 | 0/1 | TN | - |

## Synthèse synthétique (labels *synthetic*, pas produit)

### acstools.satdet
- évalués ok=3 erreur=0 timeout=0 (non évalués: positif=0 négatif=0)
- positives=2 négatifs=1
- TP=1 FP=0 FN=1 TN=1
- détection (positives)=0.5 FP rate (négatifs)=0.0
- temps: mean=0.0197s p50=0.020194763999825227s p95=0.021468497100795503s (n=3)

### acstools.findsat_mrt
- évalués ok=3 erreur=0 timeout=0 (non évalués: positif=0 négatif=0)
- positives=2 négatifs=1
- TP=2 FP=0 FN=0 TN=1
- détection (positives)=1.0 FP rate (négatifs)=0.0
- temps: mean=3.8s p50=3.811833376999857s p95=3.845786763500837s (n=3)
