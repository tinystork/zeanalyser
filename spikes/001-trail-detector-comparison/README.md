# Spike TRAIL-02A — comparaison `satdet` vs `MRT` (corpus synthétique)

**Mission** : `ZA-TRAIL-02A-SATDET-MRT-SPIKE-20261002`
**Question** : peut-on comparer honnêtement, sur le même petit corpus synthétique
déterministe et **sans toucher au produit**, (A) `acstools.satdet` (référence
historique) et (B) `acstools.findsat_mrt.TrailFinder` sur tableau 2D ? Et MRT
est-il assez faisable CPU/RAM pour justifier une évaluation ultérieure sur corpus
réel ?

**Verdict : `VALIDATED`** — la comparaison est faisable et reproductible sur le
même corpus synthétique, avec des résultats discriminants et des garde-fous
d'honnêteté respectés. MRT est faisable CPU/RAM (≈2,6 s et ≈10 Mo par image à
192 px). Aucun seuil produit, aucune promotion, aucun choix backend : le corpus
réel 100–200 et les budgets restent des gates futurs.

---

## 1. Environnement observé (déjà installé, aucune installation)

| paquet | version |
|---|---|
| `acstools` | 3.8.2 |
| `astropy` | 8.0.1 |
| `numpy` | 2.5.1 |
| `scipy` | 1.18.0 |
| `scikit-image` | 0.26.0 |
| `photutils` | 3.0.0 |
| `matplotlib` | 3.11.1 |
| Python | 3.13.5 (venv du repo, `Linux … deb13-amd64`) |

Commande d'environnement : `.venv/bin/python` (venv déjà présent dans le repo).
Aucun paquet n'a été installé/modifié.

**Santé dépendance / licence** : `acstools` 3.8.2 est **déjà installé** dans le
venv du repo (aucune installation). Licence **BSD-3-Clause** — preuve locale,
sans réseau : métadonnées `acstools-3.8.2.dist-info/METADATA`
(`License-Expression: BSD-3-Clause`, `License-File: LICENSE.md`) et fichier
`acstools-3.8.2.dist-info/licenses/LICENSE.md` (Copyright 2020, Space Telescope
Science Institute, AURA). Le texte de la licence n'est pas recopié ici.

## 2. API live observée (acstools 3.8.2)

- **satdet** : `detsat(searchpattern, chips, n_processes, sigma, low_thresh,
  h_thresh, small_edge, line_len, line_gap, percentile, buf, plot, verbose)` →
  `(results, errors)`. `results[(file, ext)]` = tableau `[N, 2, 2]` de segments
  (endpoints), ou tableau vide si « pas de satellite ». Utilisé via **FITS
  temporaires** (API publique uniquement, `n_processes=1`, `plot=False`).
- **MRT** : `TrailFinder(image, processes=…, min_length=25, max_width=75,
  buffer=250, threshold=5, theta=None, kernels=None, check_persistence=True,
  min_persistence=.5, save_catalog=…, save_diagnostic=…, save_mrt=…,
  save_mask=…)`. Pipeline `run_mrt()` → `find_mrt_sources()` →
  `filter_sources()`. Catalogue (`QTable`) : `id, xcentroid, ycentroid, theta,
  rho, endpoints, width, snr, status, persistence, …`. Utilisé **directement sur
  tableau 2D** (pas `WfcWrapper`), `processes=1`, tous les `save_*` à `False`.

## 3. Configs documentées (une par backend)

### Backend A — `acstools.satdet` (Hough probabiliste, historique)
- `sigma=2.0, low_thresh=0.1, h_thresh=0.5, percentile=(4.5, 93.0)` : défauts
  acstools conservés.
- **Ajustement de faisabilité unique (signalé)** : `line_len=size//2`,
  `line_gap=size//4`, `small_edge=20`, `buf=size//8` — les défauts
  (`200/60/75/200`) sont dimensionnés pour du plein cadre ACS (~4096×2048) et
  n'ont pas de sens sur 128–256 px.
- `chips=[0]` (PrimaryHDU), comme l'adaptateur produit « référence historique »
  (le warning `not a valid science extension` est filtré).
- « détecté » = `len(segments) > 0` (satdet ne renvoie des segments que quand il
  conclut `satellite=True`). **Plusieurs segments = une seule trace physique.**

### Backend B — `acstools.findsat_mrt.TrailFinder`
- Pré-traitement standard (documenté par l'exemple acstools) : soustraction de la
  médiane (le modèle d'erreur MRT suppose une entrée centrée).
- **Ajustements de faisabilité (signalés)** : `buffer=size//4` (défaut 250 pour
  plein cadre) ; `theta` explicite `np.arange(0, 180, step)` pour borner le coût
  (`step=1.0°` en quick, `0.5°` en full).
- `min_length=25, max_width=75, threshold=5, check_persistence=True,
  min_persistence=0.5` : défauts conservés. `processes=1`. Aucun fichier écrit.
- **Statut « accepted »** : `status == 2` (passe SNR + largeur + persistance),
  cohérent avec le défaut acstools `mask_include_status=[2]` et le plot
  diagnostic (turquoise = status 2). `status == 1` = « passe SNR+largeur mais
  échec persistance » (rapporté séparément comme *candidat*, pas *accepted*).
  `status == 0` = rejeté.
  ⚠️ *Incohérence doc/code relevée* : la docstring de `mask_include_status`
  décrit des statuts `1/2/3`, alors que `utils_findsat_mrt.filter_sources`
  produit réellement `0/1/2`. On suit le **code** (0/1/2), pas la docstring.

## 4. Corpus synthétique (déterministe, seed `20261002`)

Fond Poisson (μ=30) + bruit de lecture Gaussien (σ=3). Étoiles = PSF Gaussienne
(σ=1,5 px, pic contrôlé). Trace = section Gaussienne (σ=1,5 px, flux par cas).
12 cas (7 positifs / 5 négatifs), tailles 192 px (quick) et 256 px (full) :

| id | type | vérité terrain |
|---|---|---|
| `diag_strong` | positif | 1 diagonale forte bord-à-bord (45°) |
| `horiz_strong` | positif | 1 horizontale forte (0°) |
| `vert_strong` | positif | 1 verticale forte (90°) |
| `diag_weak` | positif | 1 diagonale faible (flux 60) |
| `diag_short` | positif | 1 diagonale courte (~40 %, intérieure) |
| `diag_partial` | positif | 1 diagonale partielle (une extrémité intérieure) |
| `two_trails` | positif | 2 diagonales (45° + 135°) |
| `noise_stars` | négatif | bruit + 15 étoiles |
| `aligned_stars` | négatif | 12 étoiles alignées (collinéaires) |
| `column_defect` | négatif | colonne chaude pleine hauteur |
| `filament_gradient` | négatif | gradient linéaire lisse (basse fréquence) |
| `dense_field` | négatif | 150 étoiles (champ dense) |

⚠️ Ces négatifs sont des **simplifications** de classes de confusion (étoiles
alignées, défaut de colonne, gradient basse fréquence, champ dense). Ils ne
prétendent **pas** reproduire tout le Seestar.

## 5. Résultats (quick, 192 px, θ=1,0°, seed 20261002)

Chiffres de synthèse (libellés **synthetic**, pas produit) :

| backend | détection (positifs) | FP (négatifs) | temps/image | ΔRSS |
|---|---|---|---|---|
| `satdet` | 2/7 (28,6 %) | 0/5 (0 %) | ~0,02 s | ~5 Mo |
| `MRT` | 5/7 (71,4 %) | 2/5 (40 %) | ~1,4 s | ~7–13 Mo |

*(Temps = moyennes du run sauvegardé `results/results_run.json` ; satdet mean
≈0,013 s, MRT mean ≈1,37 s. Variabilité système attendue entre runs — ces chiffres
sont indicatifs, pas des benchmarks stables.)*

Tableau par cas (détail complet dans `results/results_run.json`) :

| case | satdet | MRT (accepted / candidat) |
|---|---|---|
| `diag_strong` | ✅ 2 seg @45° | ✅ acc=1 @45° |
| `horiz_strong` | ❌ (0°, exclu) | ✅ acc=1 @0°/180° |
| `vert_strong` | ❌ (90°, exclu) | ✅ acc=2 @~90° (split θ 0/180) |
| `diag_weak` | ❌ | ✅ acc=1 @45° |
| `diag_short` | ❌ | ⚠️ cand=1 (status 1, persistance) |
| `diag_partial` | ❌ | ⚠️ cand=1 (status 1, persistance) |
| `two_trails` | ✅ (2 seg, 1 seul angle 45°) | ✅ acc=2 @45°+135° |
| `noise_stars` | ✅ négatif | ✅ négatif |
| `aligned_stars` | ✅ négatif | ⚠️ cand=1 (status 1, rejeté) |
| `column_defect` | ✅ négatif | ❌ **FP** acc=2 @~90° |
| `filament_gradient` | ✅ négatif | ✅ négatif (status 0) |
| `dense_field` | ✅ négatif | ❌ **FP** acc=1 (1 source parasite) |

*(✅ = comportement attendu, ❌ = échec/FP, ⚠️ = nuance à lire.)*

Point de contrôle 256 px (`results/full_spot/`, θ=0,5°, 3 cas) : `diag_strong`
et `vert_strong` ✅ détectés par MRT, `dense_field` ✅ négatif (pas de FP à cette
taille/θ — le FP « dense_field » observé en 192 px est donc **sensible à la
taille/θ**, signalé comme tel). MRT ≈3,8 s/image à 256 px (mean 3,80 s du run
sauvegardé).

## 6. Ce qui marche / ce qui surprend

**Marche**
- Les deux backends détectent la diagonale forte témoin ; MRT accepte aussi
  horizontale, verticale, faible et les deux diagonales.
- Aucun backend ne produit de FP sur bruit+étoiles ou gradient lisse.
- MRT ne crée **aucun** fichier parasite (tous `save_*` désactivés) ; satdet
  n'écrit que des FITS temporaires, supprimés ensuite.

**Surprend**
- satdet **exclut par conception** horizontales et verticales
  (`round_angle % 90 == 0`), et exige un franchissement bord-à-bord → il ne peut
  pas voir faible/court/partiel. C'est une limite de l'API historique, pas un bug.
- La **persistance** MRT rejette les traces courtes/partielles même quand
  SNR+largeur passent (`status 1`, jamais `2`) : `persistence_chunk=100` est
  dimensionné pour des traces longues de plein cadre.
- MRT **accepte une colonne chaude comme trace verticale** (FP) et produit **un
  FP dans le champ dense** (192 px) — cohérent avec la docstring acstools
  (« peut peiner sur les champs denses »).
- MRT **scinde une trace verticale en 2 sources** (θ≈88° et ≈92°) à cause de la
  coupure θ 0/180 ; une trace physique ≠ 1 source MRT.
- Incohérence doc/code sur les statuts MRT (voir §3).

## 7. Équité, mesures et limites d'interprétation

**Déterminisme des entrées** : chaque worker reconstruit **bit-à-bit** le même
array depuis `(case, seed)` (test `test_generator_deterministic`) ; l'array parent
n'est **pas** sérialisé vers le worker. Aucune transformation de vérité terrain
différente entre backends : les deux voient exactement la même image 2D.

**Prétraitement backend-native, pas une référence équitable** :
- satdet fait son propre `rescale_intensity`/percentile **interne** (aucun
  prétraitement imposé de notre côté, hormis les FITS temporaires) ;
- MRT exige une entrée centrée (soustraction de la **médiane**, pré-traitement
  standard recommandé par l'exemple acstools).
La comparaison porte donc sur des **configurations de faisabilité documentées**,
**pas** sur un benchmark équitable de backend optimisé, ni sur une validation de
performance produit.

**Tous les ajustements (une config par backend)** :
- satdet : `line_len=size//2`, `line_gap=size//4`, `small_edge=20`, `buf=size//8`
  (les défauts plein cadre 200/75/60/200 sont redimensionnés) ; `sigma`, seuils
  hysteresis, `percentile`, seuil Hough **conservés**.
- MRT : `buffer=size//4`, `theta` explicite (borné) ; `min_length`, `max_width`,
  `threshold`, `check_persistence`, `min_persistence` **conservés**.

**Ce que « runtime » mesure** : uniquement l'appel backend (`time.perf_counter`
autour de `detsat` ou `run_mrt/find_mrt_sources/filter_sources`). satdet inclut la
**lecture** FITS mais **pas** l'écriture du temp ; MRT inclut transform + catalogue
+ filtrage. `worker_wall_s` (dans le JSON brut) inclut import/startup du
sous-processus et n'est **pas** le temps backend.

**Ce que « ΔRSS » mesure** : `ru_maxrss` du sous-processus moins une baseline
« import seul ». C'est une **approximation** : si le pic d'import domine,
l'incrément algorithmique peut être **sous-estimé**. Ce n'est **pas** un pic RAM
absolu. La conclusion de faisabilité CPU/RAM reste **limitée à ce run**.

**Preuve mécanique de reproductibilité** : chaque `results_run.json` embarque un
`meta.fingerprints` (SHA-256 de `synthetic.py`, `adapters.py`, `metrics.py`,
`run_comparison.py`). `python run_comparison.py --check-results [PATH]` recharge
le JSON, vérifie le schéma, recalcule `summary` depuis `rows` (comparaison exacte
counts/rates, tolérance sur les floats), vérifie chaque paire `(case, backend)`
exactement une fois, et compare les fingerprints courants. Exit 0 si valide, nonzero
sans traceback sinon.

## 8. Reproductibilité

```bash
cd /path/to/zeanalyser
source .venv/bin/activate
# quick (défaut) : 192 px, θ=1.0°
python spikes/001-trail-detector-comparison/run_comparison.py --quick
# full : 256 px, θ=0.5°
python spikes/001-trail-detector-comparison/run_comparison.py --full
# tests spike (smoke générateur/adaptateurs/métriques)
python -m pytest spikes/001-trail-detector-comparison/test_spike.py -q
```

Sorties sous `spikes/001-trail-detector-comparison/results/` :
`results_run.json` (résultats bruts, schéma dans `adapters.py`) et
`results_summary.md`. RSS = `resource.getrusage(RUSAGE_SELF).ru_maxrss` (pic
processus enfant) moins une baseline « import seul » par backend (approximation
documentée).

## 9. Recommandation suivante

Faisabilité CPU/RAM de MRT **confirmée** → une évaluation ultérieure sur corpus
réel (100–200, budgets Tristan) est **justifiée**. À surveiller en corpus réel,
avec des garde-fous dédiés : (1) FP MRT sur défauts de colonne / champs denses ;
(2) porte de persistance à re-paramétrer pour des traces courtes ; (3) traces
verticales scindées ; (4) angles non comparables directement (convention θ MRT =
angle de projection). **Aucun choix backend** n'est fait ici : satdet reste la
référence conservative (0 FP, mais aveugle aux axes et aux traces non
bord-à-bord), MRT plus sensible mais plus permissif.

TRAIL-02B (Hough custom) n'est **pas** abordé dans cette mission — il dépendra du
verdict 02A, désormais rendu.
