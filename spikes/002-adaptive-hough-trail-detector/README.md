# Spike TRAIL-02B — Hough adaptatif (hors produit) — rework-2

**Mission** : `ZA-TRAIL-02B-ADAPTIVE-HOUGH-SPIKE-20261002` (phase `rework-2`)
**Question** : un prototype Hough adaptatif (NumPy/SciPy/scikit-image) peut-il
couvrir axes + traces courtes/partielles/multiples tout en évitant au moins les
FP synthétiques évidents de MRT (colonne chaude, champ dense), à coût assez
faible pour justifier une future évaluation sur corpus réel ?

**Verdict : `PARTIAL` (terminal)** — acquis au rework-1, non re-promu. Le
mécanisme tourne (CPU pur, aucune dépendance, aucun output parasite) et le blind
192 px reste propre (7/8 positifs, 0 FP), mais le blind 256 px garde
`soft_column_4px` FP et `offaxis_91` + `thin_38` FN. La porte « tophat »
(w90/w10) est **fragile à la ligne centrale** : elle faux-rejette de vraies
traces courtes/partielles/faibles/verticales et n'attrape pas la colonne douce à
256 px.

---

## 1. Environnement (aucune installation, aucune dépendance nouvelle)

numpy 2.5.1 · scipy 1.18.0 · scikit-image 0.26.0 · Python 3.13.5. Générateur/
adaptateurs spike-001 importés en lecture seule.

## 2. Algorithme (5 étapes)

1. **Fond/bruit** — `ndimage.median_filter` (~13 % image), σ = 1.4826·MAD.
2. **Candidats multi-échelles** — Canny (σ 1.0/2.5) + `probabilistic_hough_line`,
   `theta 0..179°` (tous les angles, y compris 0/90).
3. **Regroupement colinéaire borné** — segments → lignes → traces en
   **complete-link** (une entrée rejoint un cluster seulement si compatible avec
   tous ses membres), moyenne **circulaire** d'angle (wrap 0/180). Garantit
   `max(rho)-min(rho) <= tol` et angle pairwise ≤ tol (pas de pont transitif).
4. **Validation interprétable** — contraste, largeur, continuité, support, forme ;
   `score` ∈ [0,1] (jamais probabilité), composants loggés.
5. **Rejet d'artefacts par mesure** — colonne dure via `step_sharpness`
   (max |Δ²|/pic) ; colonne douce via `tophat` (w90/w10). Jamais d'exclusion
   d'orientation.

## 3. Corpus — trois splits

- **`dev`** — spike-001 (12 cas, seed 20261002), read-only.
- **`observed_holdout`** — holdout d'origine (13 cas, seed 20261003), **contaminé**.
- **`blind`** — figé (seed 20261004, 17 cas) ; au rework-2 il est **diagnostic**
  (le grouping a changé post-blind), pas un test de re-promotion.

## 4. Config gelée (inchangée depuis r1)

`canny_scales=[1.0,2.5]`, `canny_low/high=2.0/4.0`, `theta_step=1.0°`,
`group_angle_tol=3.0°`, `group_rho_tol=1.0px`, `trail_max_width=8.0px`,
`min_contrast_snr=6.0`, `min_continuity=0.70`, `min/max_width=1.0/9.0px`,
`max_step_sharpness=0.65`, `max_tophat=0.30`, `min_length_frac=0.30`.

**Hash config** (SHA-256) : `8493bbcce9a9d3969de51ecde20d97e796ef7f8630fe486104b002e4e2284f14`
— identique avant/après le run blind et après rework-2.

## 5. Corrections (rework-1 puis rework-2)

Rework-1 : (1) normalisation comparaison par `detected` ; (2) matching borné
angle ≤ 3° / offset ≤ 5 px ; (3) moyenne circulaire ; (4) `observed_holdout` +
`blind` ; (5) fingerprints + 001 ; (6) docstrings.

Rework-2 : (a) **TP image géométriquement matché** — ≥ 1 GT strictement dans les
tolérances ; positif hors tolérance = FN + extras (fix 1) ; (b) **clustering
complete-link borné** (fix 2) ; (c) **checker valide la comparaison 001 sauvée**
(rows = chaque case × 2 backends, summaries recalculés) (fix 3) ; (d) trace/docs
(le blind r2 est diagnostic, verdict PARTIAL terminal).

## 6. Résultats (labels *synthetic*, pas produit)

### Blind (diagnostic)

| taille | TP | FP | FN | TN | détection | FP rate | FP | FN | two_mixed |
|---|---|---|---|---|---|---|---|---|---|
| 192 px | 7 | 0 | 1 | 9 | 0.875 | 0.000 | — | thin_38 | 2/2 cohérent |
| 256 px | 6 | 1 | 2 | 8 | 0.750 | 0.111 | soft_column_4px | offaxis_91, thin_38 | 1/2 |

### dev / observed_holdout (tuning)

| split/taille | TP | FP | FN |
|---|---|---|---|
| dev 192 | 6 | 0 | diag_short |
| dev 256 | 6 | 0 | diag_partial |
| observed 192 | 5 | 0 | diag_partial_b, diag_short_b |
| observed 256 | 6 | 0 | diag_weak_b |

### Comparaison 001 (observed_holdout, in-process)

| backend | détection | FP rate | FP | FN |
|---|---|---|---|---|
| custom | ~0.71–0.86 | 0.000 | — | cf. FN |
| satdet | 0.000 | 0.000 | — | les 7 |
| MRT | 0.857 | 0.500 | aligned_stars, col 1px, col 2px | diag_short_b |

Runtime ≈ 0.45 s (192) / 1.35 s (256) ; ΔRSS ≈ 5.6 / 11.8 Mo ; 0 erreur/timeout.

## 7. Pourquoi PARTIAL — limite honnête

- **Porte `tophat` non fiable** : sensible à la ligne centrale. Faux-rejette de
  vraies traces courtes/partielles/faibles/verticales (tophat 0.33 : `diag_short`,
  `diag_partial`, `diag_short_b`, `diag_partial_b`, `diag_weak_b`, `offaxis_91`) ;
  **n'attrape pas** la colonne douce à 256 px (tophat 0.14). Le correctif de
  grouping (complete-link) a déplacé les lignes centrales et révélé cette fragilité.
- **Colonne douce 4 px non résolue** : TN à 192 px (fragmentation), FP à 256 px.
- **Trace fine (σ ≲ 1.2 px) indistinguable d'une colonne 1 px** : `thin_38` FN.
- Colonnes dures, champ dense, étoiles alignées, dashes, filament, gradient :
  rejetés aux deux tailles (robuste).

## 8. Reproducibilité

```bash
cd /path/to/zeanalyser
source .venv/bin/activate
python -m pytest spikes/002-adaptive-hough-trail-detector/test_spike.py -q   # 42 tests
python spikes/002-adaptive-hough-trail-detector/run_spike.py --quick --compare-001
python spikes/002-adaptive-hough-trail-detector/run_spike.py --full --compare-001
python spikes/002-adaptive-hough-trail-detector/run_spike.py --check-results
```

## 9. Prochaine étape recommandée

Plusieurs briques tiennent aux deux tailles (diagonales, colonne dure, champ
dense), mais l'ensemble n'est pas stable : la trace fine échoue aux deux tailles,
et à 256 px la quasi-verticale échoue tandis que la colonne douce devient un FP.
Le mécanisme prioritaire à explorer est donc le remplacement du top-hat par seuil
de largeur par une mesure robuste au sous-pixel (ajustement Gaussien + résidu, ou
kurtosis), puis une re-validation sur un nouveau blind. Aucun choix backend,
aucune intégration produit, aucune performance Seestar n'est autorisé.
