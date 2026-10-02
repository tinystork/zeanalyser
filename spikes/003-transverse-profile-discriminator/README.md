# Spike TRAIL-02C — profil transverse (discriminateur de forme)

**Mission** : `ZA-TRAIL-02C-TRANSVERSE-PROFILE-SPIKE-20261002`
**Question** : un échantillonnage bilinéaire sous-pixel du profil transverse +
comparaison explicite de modèles (crête lisse Gaussienne vs plateau/colonne
adoucie) peut-il remplacer la porte `tophat` fragile de TRAIL-02B, préserver
traces fines/quasi-axes et rejeter colonnes dures/douces aux deux tailles, sans
tuning sur le blind ?

**Verdict : `PARTIAL`** (mécanisme seulement — aucun backend produit, aucune
intégration, aucun claim Seestar). Voir `results/results_summary.md` et le
rapport de mission (hors dépôt) pour les chiffres.

---

## 1. Environnement (aucune installation, aucune dépendance nouvelle)

numpy 2.5.1 · scipy 1.18.0 · scikit-image 0.26.0 · Python 3.13.5. Le mécanisme
n'utilise que NumPy/SciPy déjà présents dans le venv. Spike-002 et spike-001 sont
importés **en lecture seule** (aucune modification).

## 2. Mécanisme (3 étapes, hors produit)

1. **Échantillonnage sous-pixel** — `sample_transverse_profile_subpixel` via
   `scipy.ndimage.map_coordinates(order=1)` (bilinéaire), jamais `round(x,y)`,
   réduction longitudinale robuste (médiane). Retourne profil + coverage.
2. **Ajustement de deux modèles bornés** (`least_squares`, plusieurs départs) :
   * `ridge` — `baseline + A*exp(-0.5*((x-c)/s)^2)`, sigma borné [0.3, 10].
   * `column` — plateau box lissé par différence de sigmoïdes logistiques,
     `centre/largeur/softness` bornés.
3. **Comparaison de qualité normalisée** — RSS réduit + AICc (si n suffisant),
   score de préférence **signé** dans (-1,1) (jamais probabilité). Décision
   `ridge | column | ambiguous`. `ambiguous` est une réponse honnête de premier
   rang (delta insuffisant, fit mauvais, ou non-convergence) — jamais promu.

Garde-fous : non-convergence ⇒ `ambiguous` (jamais accept par défaut) ; un fit
« colonne » dégénéré (largeur épinglée au plancher, pas de plateau résoluble
`width > 2*softness`) n'est **pas** promu en `column`.

## 3. Corpus profil — deux splits déterministes

* `dev` (seed 20261005) : grille petite déterministe — ridges gaussiennes
  sigma 0.6/0.8/1.2/1.5/2.5/3.5, centres sub-pixel 0/.25/.5/.75, angles
  axes+diagonales, amplitudes/bruits variés ; colonnes/rows largeur 1/2/4/6,
  softness 0/.5/1/2 ; cas sans structure/double ridge/étoiles alignées/gradient/
  asymétrique. Utilisé **uniquement** pour choisir le seuil (≤ 2 essais).
* `blind` (seed 20261006) : combinaisons **non vues** — sigma 0.7/1.0/1.8/3.0,
  centres .125/.375/.625 ; colonnes largeur 1.5/3/5, softness .25/.75/1.5 ;
  fond gradient + profil asymétrique. Labels pré-assignés avant run selon une
  règle physique documentée (`column` ssi `softness==0 or width>2*softness`,
  sinon `ambiguous` pour un plateau indiscernable d'une crête).

## 4. Config gelée (inchangée avant/après blind)

`sample_order=1`, `sample_half_width=10`, `sample_offset_step=0.25`,
`min_snr=4.0`, `max_rss_frac=0.10`, `pref_delta_threshold=0.10`,
`aicc_delta_threshold=4.0`, `column_flat_top_ratio=2.0`, bornes sigma/largeur/
softness. **Hash config** (SHA-256) : `CONFIG` sérialisé trié — voir
`run_spike._config_sha()` ; embarqué dans chaque `results_run.json`.

**2 essais DEV documentés** (choix de seuil, jamais sur blind) :
1. seuil de préférence réduit seul (préférence RSS réduite) — sépare mais
   confond crête fine vs plateau étroit ;
2. ajout AICc comme signal primaire + garde `column_flat_top_ratio` (un fit
   colonne dégénéré sans plateau résoluble n'est pas un `column`).

Aucun changement après le premier run blind.

## 5. Résultats (labels *synthetic*, pas produit)

### Profil (blind)

| classe | ridge | column | ambiguous |
|---|---|---|---|
| ridge GT (12) | 8 | 3 | 1 |
| column GT (6) | 0 | 6 | 0 |
| ambiguous GT (8) | 2 | 3 | 3 |

- ridge recall = 0.667, column recall = 1.0 ; runtime profil p50 ≈ 0.08 s.
- **Limites d'identifiabilité publiées** : crête large σ3.0 faible SNR → colonne ;
  colonne 1 px → crête ; plateau très adouci (w1.5 b1.5, w3 b1.5) → crête.

### End-to-end (sonde baseline 002 vs probe 003, fail-closed)

| taille | backend | TP | FP | FN | TN |
|---|---|---|---|---|---|
| 192 | 002 baseline | 7 | 0 | 1 (thin_38) | 9 |
| 192 | 003 probe | 7 | 1 (hard_col1) | 1 (wide_141) | 8 |
| 256 | 002 baseline | 6 | 1 (soft_col4) | 2 (offaxis_91, thin_38) | 8 |
| 256 | 003 probe | 7 | 1 (hard_col1) | 1 (thin_38) | 8 |

La sonde (fail-closed) résout les colonnes douces (soft col 4 blur1 / 6 blur2) et
`offaxis_91` / `thin_s06_38`, mais **régresse sur la colonne dure 1 px**
(indiscernable d'une crête fine au profil) et **défère** `wide_141` (σ3.5) à
192 px en `ambiguous` (refusé par la shape seule, donc FN) — coût honnête du
fail-closed. `thin_38` reste FN à 256.

## 6. Pourquoi PARTIAL — limite honnête

Le modèle sépare **proprement** au niveau profil (column recall 1.0, colonnes
dures ≥2 px et douces rejetées), mais deux limites d'identifiabilité demeurent :
(1) **colonne dure 1 px ≈ crête fine** (σ ≲ 0.8) : le profil transverse seul ne
les distingue pas — c'est exactement la borne `thin_38`/`hard_col1` héritée de
002 ; (2) **crête large faible SNR ≈ colonne adoucie**. Ces cas sont signalés
`ambiguous` au niveau profil quand le delta le permet.

**Correction (rework-1)** : une colonne **continue** de 1 px et une trace
verticale fine **continue** sont toutes deux pleine trame — la continuité ou le
support longitudinal **ne suffit donc pas** à les départager, contrairement à ce
que laissait entendre une formulation antérieure. La morphologie mono-image peut
être **non identifiable** pour cette paire. La continuité reste utile contre les
étoiles alignées et les dashes discontinus, pas contre une colonne continue.
Preuve complémentaire nécessaire à évaluer (décision architecture/corpus, pas un
simple seuil) : contexte multi-frame en coordonnées détecteur (défaut fixe vs
ciel/traînée qui bouge), carte bad-pixel/calibration, ou métadonnée capteur.

## 7. Reproductibilité

```bash
cd /path/to/zeanalyser
source .venv/bin/activate
python -m pytest spikes/003-transverse-profile-discriminator/test_spike.py -q   # 32 tests
python spikes/003-transverse-profile-discriminator/run_spike.py --dev
python spikes/003-transverse-profile-discriminator/run_spike.py --blind
python spikes/003-transverse-profile-discriminator/run_spike.py --probe
python spikes/003-transverse-profile-discriminator/run_spike.py --probe --full
python spikes/003-transverse-profile-discriminator/run_spike.py --check-results
```

Sorties sous `spikes/003-transverse-profile-discriminator/results/` :
`results_run.json` + `results_summary.md`. Le checker recharge le JSON, vérifie
schéma, recalc summaries/paires, compare config gelée + fingerprints (y compris
les fichiers 002/001 importés).

## 8. Prochaine décision

Le mécanisme de comparaison de modèles est **validé comme remplacement du
tophat au niveau profil** (colonnes douces rejetées proprement), mais il ne peut
pas, à lui seul, départager colonne 1 px / crête fine ni crête large faible SNR
— et la continuité mono-image ne le peut pas non plus pour une colonne continue.
Décision attendue de Jarvis : (a) **borne d'identifiabilité mono-image acceptée**
(`ambiguous` explicite) + évaluer un contexte **multi-frame en coordonnées
détecteur** (défaut fixe vs traînée mobile), une **carte bad-pixel/calibration**
ou une **métadonnée capteur** — ceci peut être une décision d'architecture/corpus,
pas un seuil ; ou (b) conserver 002 pour ces bornes et n'utiliser 003 que pour les
colonnes douces. Aucun choix backend, aucune intégration, aucune performance
Seestar autorisé.
