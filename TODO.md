# TODO — ZeAnalyser

Mis à jour le **2026-10-01**. Branche de travail : **beta**.

Ce fichier est le tableau de bord des deux prochains chantiers : **traînées** et
**transparence / voile nuageux**. Il distingue les prérequis, les critères de
validation et les dettes indépendantes. Une case cochée indique une preuve
acquise, pas simplement du code présent. Aucun nouveau chantier scientifique
n'a été implémenté lors de sa rédaction.

## 1. État de départ vérifié

- [x] Références distantes actualisées ; `beta` locale avancée en fast-forward
  vers `origin/beta`, sans nouvelle fusion de fonctionnalités.
- [x] Base scientifique et applicative : `38184521997b77553fd854c454065c17ed1ead2a`
  (`origin/beta` et `origin/main` au même SHA lors de l'inspection), version **3.4.0**.
- [x] Instrumentation de performances P2.0 (`e9158e7`) et progression P2.0.1
  (`3818452`) déjà intégrées : ne pas les remettre dans le backlog d'implémentation.
- [x] Correctifs précédents présents : réouverture des projets, annulation,
  sécurité des actions sur fichiers, zoom, métriques FWHM/ECC et source canonique
  des résultats. Les témoins d'identité Windows/Linux avaient été clôturés ;
  ne pas rouvrir ce chantier sans nouvelle régression.
- [x] Baseline initiale Linux/Python 3.13 reproduite dans le `.venv`, Qt
  offscreen, préférences XDG et répertoire courant temporaires : **200 passed,
  1 failed, 70 warnings en 44,83 s** (temps externe 48,09 s).
- [x] Baseline entièrement verte après BASE-01 : **209 passed, 70 warnings en
  35,35 s**, rejoués indépendamment par Junior dans un cwd et des répertoires
  XDG temporaires. Les warnings préexistants restent à traiter séparément.

L'ancien échec `test_project_tab_file_pickers_and_analyse_enable` n'a **pas** été
reproduit dans cette exécution isolée. Ne pas le déclarer encore défectueux,
ni considérer qu'une correction produit a été faite : surveiller son isolation.
Les tests de GUI existants ne prouvent pas à eux seuls l'efficacité d'un détecteur.

## 2. Avant les nouveaux algorithmes : stabilisation courte

### BASE-01 — Aperçu et baseline de tests — ACCEPTÉ le 2026-10-01

- [x] Corriger le chemin de `_load_preview_from_row` : les formes `file_path`
  explicite, `path` canonique complet et ancien dossier + nom sont résolues par
  une fonction commune au chargement et à la navigation inverse. Une ligne
  canonique absente ne devient plus `image.fits/image.fits`.
- [x] Actualiser le test d'aperçu au contrat réel de **ZeViewer asynchrone** :
  `_preview_last_histogram` reste `None` dans le parent par construction ; vérifier
  réellement la fin du chargement, l'image et l'histogramme dans le propriétaire actuel.
  Ne pas simplement supprimer l'assertion ou ignorer le test.
- [x] Couvrir une vraie ligne issue de l'analyse, FITS/PNG, chargement invalide,
  sélection rapide et réouverture ; ne pas tester seulement l'ancien `file_path`.
- [x] Relancer la suite avec préférences isolées et obtenir une baseline verte.

**Preuves :** 43 tests ciblés d'aperçu/viewer/réouverture/canonical passés par
Junior ; suite complète 209/209 ; Nono review-0 **ACCEPT** sans finding
BLOCKER/HIGH/MEDIUM. Réserve LOW acceptée : une forme legacy pathologique où
le dossier porte exactement le même nom que le fichier reste ambiguë ; le
contrat canonique et le cas fichier manquant sont déterministes et testés.
**Gate :** image/histogramme réels chargés depuis le chemin canonique et erreur
visible si chargement impossible. Ce socle est nécessaire à la vérification
visuelle des futures surimpressions.

### BASE-02 — Observables scientifiques fiables — ACCEPTÉ le 2026-10-01

- [x] Ne plus retourner `starcount=0` pour toute exception interne : résultat
  structuré distinguant mesure valide, absence réelle de détections et erreur.
  Préserver les valeurs SNR/FWHM/ECC valides si une seule mesure échoue.
- [x] Propager cette distinction jusqu'au tableau, logs, exports et réouverture.
  Aucun rejet « nuages » sur une mesure échouée ou non effectuée.
- [x] Qualifier les `ComplexWarning` observés dans `ecc_module.py:200–201` :
  covariance réelle symétrique désormais traitée avec `eigvalsh`, gardes
  physiques testées et relation FWHM historique conservée ; aucun filtre global.
- [x] Préparer la compatibilité des paramètres DAOStarFinder dépréciés
  (`sharplo/sharphi`, `roundlo/roundhi`) sans changer leurs valeurs scientifiques.

**Gate :** faux « zéro étoile » impossible sur erreur ; métriques utilisées pour
écarter un problème de PSF documentées et testées. La correction starcount fait
partie du socle de la nouvelle mission, pas d'un grand chantier préalable séparé.

**Preuves :** 64 tests ciblés puis suite complète isolée **241 passed / 39
warnings** rejoués par Junior ; vraie API de réouverture, pool/fallback,
agrégation et recommandation Qt couverts. Nono review-0 **ACCEPT** sans finding
BLOCKER/HIGH/MEDIUM. Réserve LOW : `ecc_module.py` conserve des fins de ligne
mixtes CRLF/LF historiques, à normaliser dans un changement d'hygiène séparé.

### BASE-03A — Contrats communs et format corpus — ACCEPTÉ le 2026-10-01

- [x] Définir des résultats versionnés : état, mesures, raisons, backend/version,
  paramètres effectifs, transformations de coordonnées et unités.
- [x] Distinguer `détecté`, `négatif mesuré`, `indéterminé`, `erreur`, `ignoré`,
  `indisponible` ; ne pas transformer implicitement les anciens `False` en
  preuve d'une analyse négative réussie.
- [x] Préparation 2D CFA/RGB/mono documentée, pixels invalides/saturation/HDU
  gérés ; préserver les originaux et la photométrie. La vue étirée n'est pas
  l'entrée scientifique. Partager les primitives, pas imposer un même
  prétraitement final aux deux détecteurs.
- [x] Définir le format du corpus annoté partagé, les labels, la double revue
  et la séparation anti-fuite par session/cible ; manifestes et exemples v1
  syntaxiquement vérifiés, sans image ni chemin privé dans le dépôt.
- [ ] Peupler le corpus réel initial avec 100–200 images, puis étendre les
  négatifs pour mesurer les faux positifs rares ; conserver les cas incertains.
  Ce gate est requis avant sélection/promotion d'un backend, pas avant TRAIL-01.
- [x] Définir portée, protocole de benchmark, budgets temps/RAM relatifs et
  critères mesurables avant chaque
  tâche d'implémentation. CPU en premier, concurrence bornée, pas de modèle ML
  ou de nouvelle dépendance lourde sans nécessité démontrée.

**Preuves :** contrats résultat/corpus v1, deux schémas Draft 2020-12, six
exemples, protocole benchmark et 32 tests documentaires ; suite complète
isolée **273 passed / 39 warnings** rejouée par Junior. Nono review-0
**ACCEPT**, aucun finding BLOCKER/HIGH/MEDIUM. Limite LOW acceptée : verrou
stdlib ciblé, pas de validation JSON Schema complète (`jsonschema` absent et
non ajouté). Les valeurs candidates p95/RSS et les seuils trails proposés
restent à confirmer par Tristan avant promotion, pas avant réparation TRAIL-01.

## 3. TRAIL — Détection des traînées

### TRAIL-01 — Réparer l'intégration existante avant de juger le moteur — ACCEPTÉ le 2026-10-02

- [x] Normaliser les clés `(filename, extension)` de **résultats et erreurs**
  acstools ; le chemin normal fournit une liste mais cherche actuellement des
  clés `filename` seules et perd les détections positives.
- [x] Unifier `low_thr/high_thr` Qt avec `low_thresh/h_thresh` backend ; définir
  les unités 0..1 ou pourcentages explicitement. Qt propose 10/50 et 0..10000,
  le backend attend 0..1. Renommer les clés ne suffit pas.
- [x] Migrer/valider les anciens réglages sans deviner leurs unités ; journaliser
  les paramètres réellement reçus.
- [x] Tests de bout en bout GUI → options → moteur → tableau → export/réouverture :
  positif, négatif, erreur, absent, annulation, chemins contenant des caractères de glob.
- [x] Refaire le témoin numérique : diagonale synthétique détectée par acstools
  **et** marquée positive par la chaîne applicative.

**Preuve de départ :** acstools 3.8.2 a détecté 4 segments sur la diagonale,
mais `perform_analysis` a produit `has_trails=False, num_trails=0`. Un backend
simulé toujours positif confirme indépendamment le défaut de contrat.

**Résultat accepté :** paramètres Qt 0–100 % convertis vers les fractions
canoniques ; migration legacy journalisée ; sorties/erreurs multi-extension
normalisées ; états fail-safe (aucun faux négatif sur erreur/absence) ; actions
uniquement sur positif ; filtres/graphes Qt et Tk cohérents ; réouverture JSON
préservée. Un chemin littéral contenant des métacaractères glob est échappé.
Témoin réel acstools 3.8.2 : `diag[1].fit` → `measured_positive`, 6 segments,
action différée. Gates finales : **305 passed / 45 warnings**, diff-check vert ;
Nono review-1 **ACCEPT**, aucun BLOCKER/HIGH/MEDIUM. LOW accepté : EOL mixtes
historiques dans `trail_module.py`/`zone.py`, sans erreur de diff.

### TRAIL-02 — Choisir un détecteur adapté sur des preuves

**TRAIL-02A — spike satdet vs MRT accepté le 2026-10-02 :** comparaison
synthétique déterministe et mécaniquement vérifiable, sans changement produit.
Sur 7 positifs / 5 négatifs simplifiés : satdet détecte 2/7 avec 0/5 FP ; MRT
détecte 5/7 avec 2/5 FP. MRT est techniquement testable mais n'est **pas**
sélectionné. Le corpus réel annoté et les budgets confirmés restent obligatoires.
Artefacts : `spikes/001-trail-detector-comparison/` ; gates : 30 tests spike,
305 tests produit isolés, Nono review-1 ACCEPT.

**TRAIL-02B — spike Hough adaptatif accepté `PARTIAL` le 2026-10-02 :** pipeline
CPU complet sous `spikes/002-adaptive-hough-trail-detector/`, sans intégration
produit. Après matching géométrique et grouping complete-link : blind diagnostic
192 px = 7/8 positifs, 0/9 FP ; 256 px = 6/8 positifs, 1/9 FP. Bloqueurs :
trace fine perdue, quasi-verticale perdue à 256 px et colonne douce 4 px acceptée.
La porte transverse top-hat est sensible au sous-pixel ; elle doit être remplacée,
pas retunée. Gates : 42 tests spike, checks quick/full + fingerprints/comparaison,
305 tests produit isolés, Nono ACCEPT sur le verdict `PARTIAL`.

**TRAIL-02C — spike profil transverse accepté `PARTIAL` le 2026-10-02 :**
échantillonnage bilinéaire sous-pixel et comparaison ridge gaussien / plateau
adouci sous `spikes/003-transverse-profile-discriminator/`. La sonde fail-closed
rejette les colonnes douces et améliore certains axes, mais confond encore une
colonne continue 1 px avec une crête verticale fine et diffère certaines crêtes
larges/fines. Ce cas peut être non identifiable en morphologie mono-image ; la
prochaine preuve doit évaluer contexte multi-frame en coordonnées détecteur,
carte bad-pixel/calibration ou métadonnée capteur. Gates : 39 tests spike, trois
artefacts mécaniquement vérifiés, 305 tests produit isolés, Nono review-1 ACCEPT.

**Premier lot réel positif — 2026-10-02 :** 7 FITS Seestar CFA GRBG 2 MP,
sélectionnés visuellement par Tristan de la trace la plus claire à la plus ténue.
Le produit satdet par défaut en détecte 2/7 ; des seuils abaissés produisent des
lignes parasites massives et ne constituent pas un 7/7 valide. MRT accepte le
cas clair mais manque le vertical à ~120 s/image ; Hough 002 dépasse 180 s sur
une trame native. Rapport privé conservé hors dépôt projet (non publié).
Il manque encore géométries GT et négatifs de la même session avant benchmark.

- [x] Garder `satdet` réparé comme référence historique, sans fork/monkeypatch
  de fonctions privées. Documenter ses limites : seuil Hough fixe 210,
  exclusion des angles proches des axes, dominante seule, proximité de deux bords.
- [x] Évaluer un Hough adapté avec SciPy/scikit-image déjà présents : fond/bruit,
  candidats multi-échelles, tous les angles, regroupement colinéaire, validation
  du contraste, largeur, continuité et support longitudinal.
- [x] Évaluer le remplacement du discriminateur top-hat fragile par une
  comparaison de profil transverse robuste au sous-pixel ; revalidation sans
  retuning effectuée, verdict `PARTIAL` et limites d'identifiabilité publiées.
- [x] Valider sur synthétique l'API `acstools.findsat_mrt.TrailFinder` (tableau
  2D), **pas WfcWrapper**, son coût borné et ses échecs évidents (colonne/champ dense).
- [ ] Comparer MRT sur le corpus réel annoté : intérêt potentiel sur signaux
  faibles, coût CPU/RAM et champs denses à mesurer.
  Le gain annoncé dans le contexte Hubble n'est pas acquis pour le Seestar.
- [ ] Inclure diagonales, axes, traces faibles/courtes/partielles/multiples,
  avions, étoiles alignées, défauts de suivi, filaments et colonnes défectueuses.
- [ ] Distinguer nombre de segments et nombre de traces physiques ; conserver
  les coordonnées à pleine résolution.
- [ ] Mesurer rappel/localisation, faux positifs, temps p50/p95, pic RAM et
  stabilité. Injections sur fonds réels en complément, pas à la place de vraies traces.
- [ ] Choisir un backend par défaut sur le jeu de validation tenu à l'écart ;
  n'ajouter un repli MRT que si le gain justifie sa complexité.

**Objectifs proposés, à confirmer :** rappel ≥95 % sur traces nettes annotées,
faux positifs ≤1 % sur négatifs représentatifs ; traces faibles rapportées
séparément, tailles d'échantillons et incertitudes publiées. Ce ne sont pas des
performances déjà obtenues.

### TRAIL-03 — Intégration et qualification

- [ ] Surimpression des segments/largeurs ; raisons de validation/rejet et
  score interprétable, pas une probabilité non étalonnée.
- [ ] Interface simple avec unités cohérentes ; contrôles experts séparés.
- [ ] Bilan demandées/exécutées/positives/négatives/erreurs/ignorées, y compris
  images exclues en amont par un autre filtre.
- [ ] Analyse distincte de l'action sur fichiers ; signalement seul pendant
  qualification. Pas de déplacement/suppression automatique sur résultat incertain.
- [ ] Témoin du point d'entrée installé et d'un lot réel, annulation et réouverture.

**Hors périmètre initial :** masque de pixels destiné au stacker, réparation
ou inpainting, identification certaine satellite vs avion. Un éventuel masque
nécessitera un contrat inter-produit distinct (DQ, poids, coordonnées).

## 4. CLOUD — Transparence relative et voile probable

### CLOUD-01 — MVP sur lots homogènes d'un même champ

- [ ] Réutiliser Photutils/Astropy/SciPy ; ne pas ajouter immédiatement un
  classifieur all-sky ou une nouvelle dépendance comme SEP.
- [ ] Grouper par instrument, filtre, gain, pose, binning/lecture, calibration
  et recouvrement du champ. Configurations inconnues/incomparables : pas de
  ratio arbitraire d'ADU.
- [ ] Construire une référence relative sur plusieurs poses favorables ;
  documenter son origine et sa qualité. « Meilleure du lot » ne signifie pas
  « ciel absolument clair ».
- [ ] Apparier les mêmes étoiles malgré translation/rotation/dithering ;
  WCS si disponible, sans imposer un solveur sur chaque pose.
- [ ] Mesurer les flux au-dessus du fond local, normalisés à la pose lorsque
  pertinent ; photométrie forcée aux positions attendues pour éviter le biais
  des seules étoiles brillantes encore détectées.
- [ ] Exclure saturation, bords, pixels invalides, traces et étoiles variables ;
  contrôler la PSF/énergie capturée dans les ouvertures.
- [ ] Estimer transmission relative robuste, incertitude, nombre et répartition
  des étoiles, fraction de sources attendues retrouvées.

**Gate :** atténuation contrôlée récupérée à une tolérance liée au bruit,
comparaison réelle validée ; pas de diagnostic nuage automatique sur erreur,
champ pauvre, changement de pose, mauvaise MAP ou défaut de suivi.

### CLOUD-02 — Voile partiel, explication et abstention

- [ ] Croiser transmission, fond/bruit/gradients, halos, FWHM/excentricité et
  cohérence temporelle ; considérer altitude/airmass si disponibles.
- [ ] Carte par zones seulement si densité stellaire suffisante ; conserver
  explicitement les régions indéterminées.
- [ ] Distinguer « normal relativement au lot », « voile probable »,
  « dégradation non attribuée », « indéterminé » et « erreur ».
- [ ] Ne pas utiliser « fond clair = nuages » : nuages sombres, Lune, pollution
  lumineuse, nébuleuses, buée et extinction sont des cas de confusion.
- [ ] Pas de `cloud_percent` sans définition/étalonnage ; une baisse de
  transmission ne prouve pas une cause météorologique.
- [ ] Courbe temporelle, référence utilisée, indices explicatifs et carte de
  fiabilité visibles ; séparer présence de voile et intérêt de conserver la pose.

### CLOUD-03 — Validation et extensions

- [ ] Corpus : clair, voile uniforme/partiel, entièrement voilé, champs denses
  et pauvres, nébuleuses, Lune/pollution, MAP/suivi et buée si disponible.
- [ ] Validation indépendante par session/cible : rappel, faux positifs et
  taux d'abstention séparés ; pas de rejet forcé d'une fraction d'un lot clair.
- [ ] Lots entièrement voilés / référence inadéquate : résultat relatif ou
  indéterminé, jamais certification de ciel clair.
- [ ] Temps/RAM et annulation vérifiés sur lot ; erreurs visibles jusqu'à la
  réouverture ; pas d'action destructive automatique pendant qualification.
- [ ] **Extension ultérieure** : mosaïques avec références par recouvrement,
  puis images isolées avec catalogue/détectabilité ou abstention explicite.

**Hors périmètre initial :** détecteur universel toutes images, solaire/lunaire/
planétaire sans étoiles, entraînement ML, météo d'observatoire et commande de toit.

## 5. Dette existante indépendante — ne pas tout bloquer dessus

### PERF-01 — P2.1 : témoin Windows puis optimisation ciblée

- [ ] Reproduire le ralentissement réel des grands lots Windows avec
  `ZEANALYSER_PERF_DIAG=1` ; conserver mémoire hôte, I/O, durée et contexte.
- [ ] Ne pas présenter une cause Windows comme prouvée : les témoins Linux
  1k–20k n'ont pas établi de ralentissement logiciel monotone ; le creux transitoire
  observé était corrélé à une pression mémoire hôte.
- [ ] Selon preuve, borner les futures en vol (toutes soumises d'emblée actuellement),
  puis envisager écritures de log groupées et gestion de l'historique GUI.
- [ ] Éviter le parallélisme imbriqué entre workers image et MRT.

**Priorité :** non bloquant pour petits témoins scientifiques ; qualification
obligatoire avant de promettre les nouveaux détecteurs sur 10k–20k images.

### MAINT-01 — CI, packaging et dépendances

- [ ] Étendre le workflow actuel (macOS/Python 3.11, push `main` et PR) aux
  validations pertinentes sur `beta`, Linux et Windows ; il n'y a pas de
  validation dédiée au push beta dans le workflow inspecté.
- [ ] Tester le wheel réellement installé / point d'entrée, pas seulement
  les imports du checkout ; déclarer les versions de dépendances qualifiées.
- [ ] Traiter les dépréciations Photutils/Qt et vérifier la fermeture des figures
  Matplotlib (warning >20 figures pendant la suite), sans refonte préventive.

**Priorité :** CI beta recommandée tôt ; matrice et packaging requis avant
publication des nouvelles fonctionnalités, pas avant la rédaction des prototypes.

### LEGACY-01 — Ancien couplage ZSSS et documentation

- [ ] Inventorier les consommateurs avant retrait des méthodes backend restantes
  (`send_reference_to_main`, `_run_stacking_script`, sondes `token.zsss`, etc.).
- [ ] Mettre en cohérence `docs/zeanalyser_process_contract.md` et son test avec
  le retrait déjà réalisé des boutons Qt « Analyze and Stack » / « Send Reference ».
  Ne pas casser un consommateur ni réactiver l'ancien flux implicitement.
- [ ] Conserver le périmètre produit : ZeAnalyser analyse/exporte un Stack Plan,
  le stacker empile. Tk/historiques et scripts annexes restent une tâche distincte.
- [ ] Compléter le changelog depuis les corrections post-3.4.0 ; finir au besoin
  l'i18n des commentaires d'action et de la prose des logs.

**Priorité :** dette réelle mais non bloquante pour traînées/transparence.
Aucun nettoyage massif ou retrait de fonctionnalité dans ces deux chantiers.

## 6. Ordre recommandé et invariants

1. **BASE-01** : aperçu fiable et baseline verte.
2. **BASE-02 / BASE-03** : états scientifiques fiables, contrats et corpus ;
   ces travaux peuvent avancer avec **TRAIL-01**.
3. **TRAIL-02 / TRAIL-03** : comparaison puis intégration du détecteur retenu.
4. **CLOUD-01**, puis **CLOUD-02 / CLOUD-03** : transparence sur lots homogènes.
5. Qualification grands lots/plateformes avant promotion ; dette legacy séparée.

À chaque tâche : périmètre borné, preuves reproductibles, résultats attendus
mesurables, revue du diff et des tests. Protéger les métriques existantes,
annulation, sécurité fichiers, source canonique des résultats, réouverture et
Stack Plan. Aucun changement silencieux de formule scientifique ou de protocole
inter-produit ; aucun rejet automatique fondé sur une erreur de détection.

## 7. Sources et preuves

Audits locaux du 2026-10-01, conservés hors dépôt (preuves locales, non publiées) :

- `audit-plan.md`
- `clouds-research.md`
- même dossier : `probe.py`, `probe-results.json`, `beta-baseline-pytest.log`,
  `beta-baseline-pytest.json`, `preview-path-probe.json`.

Ces fichiers sont des preuves locales, pas des dépendances runtime du projet.
Le présent TODO est autonome pour les tâches et critères d'acceptation.

Références algorithmiques :

- [acstools satdet](https://acstools.readthedocs.io/en/latest/satdet.html)
  et [TrailFinder MRT](https://acstools.readthedocs.io/en/latest/findsat_mrt.html)
  (source/docstrings installés 3.8.2 étudiés, pas de benchmark Seestar MRT).
- [Cloudynight](https://github.com/mommermi/cloudynight) : all-sky/LightGBM,
  explicitement non plug-and-play.
- [all_sky_cloud_detection](https://github.com/tudo-astroparticlephysics/all_sky_cloud_detection) :
  étoiles attendues vs détectées.
- [PyASB](https://github.com/mireianievas/PyASB) : photométrie plein ciel.
- [Photutils](https://photutils.readthedocs.io/) : briques de mesure déjà disponibles.

**Prochaine tâche unique recommandée : constituer le corpus réel annoté et
trancher l'architecture des défauts capteur (mono-image indéterminé vs contexte
multi-frame / carte bad-pixel) avant sélection du backend TRAIL.**
Ce fichier prépare les missions ;
il n'autorise ni ne constate leur réalisation, publication ou déploiement.
