# Future development — apprentissage visuel de la qualité astronomique

**Date :** 2026-10-03. **Statut : PLAN / NON IMPLÉMENTÉ.**
**Branche d'étude :** `test` locale, créée depuis `beta` à `c0f7a3b` (3.5.0).
Le checkout produit reste sur `beta`. L'ancienne référence distante `origin/test`
n'a pas été modifiée et n'est pas suivie par cette branche locale.

## 1. Intention et limites du produit

Transformer le viewer intégré en atelier d'annotation : l'utilisateur signale
une traînée, son type lorsqu'il est identifiable, une obstruction ou un voile ;
ces annotations alimentent un corpus puis un entraînement **séparé et explicite**.
Un candidat validé peut ensuite assister l'analyse des poses suivantes.

Objectifs :

- localiser les traînées et obstructions, pas seulement classer une image ;
- proposer `satellite`, `aircraft` ou `unknown` pour les traînées ;
- repérer le voile probable, avec contexte photométrique/temporel si nécessaire ;
- fonctionner en inférence sur CPU TinyDebian et, en option, GPU RTX 3070 Laptop ;
- conserver une explication visuelle, l'incertitude et les corrections humaines.

Non-objectifs initiaux : apprentissage silencieux à chaque clic, entraînement
complet obligatoire sur TinyDebian, remplacement automatique de satdet/photométrie,
rejet/suppression automatiques, inpainting, contrôle de toit, cloud distant,
détecteur universel solaire/planétaire ou certitude météorologique.

**Limites d'identifiabilité :** une traînée continue ne prouve pas « satellite » ;
une traînée pointillée ne prouve pas toujours « avion ». Nuage, buée et extinction
peuvent se ressembler ; colonne capteur et trace verticale peuvent être ambiguës
sur une seule pose. Le réseau ne crée pas une information absente : conserver
`unknown`/`indeterminate`, utiliser la couleur native et/ou des poses voisines
lorsque disponibles, ne pas imposer une classe au hasard.

## 2. Modèle léger proposé et sélection

### Premier candidat : LR-ASPP + MobileNetV3-Large (TorchVision)

- Architecture de segmentation disponible, code TorchVision **BSD-3-Clause**.
- Référence upstream : **3 221 538 paramètres**, fichier de poids annoncé
  **12,49 MB**, avec la tête de référence à classes VOC. Le nombre et la taille
  changent après adaptation des sorties ; le fichier n'est pas la RAM d'exécution.
- Poids de segmentation existants entraînés sur un sous-ensemble COCO avec
  catégories VOC : **ils ne détectent pas nos défauts astronomiques sans entraînement**.
- Comparer initialisation encodeur ImageNet / poids segmentation adaptés,
  remplacer les têtes et fine-tuner sur notre domaine. Mesurer le transfert réel.
- Faiblesse possible : résolution interne basse et disparition des traits fins.
  La légèreté ne vaut pas preuve d'adéquation ; gate explicite sur les traces 1–2 px.

### Challenger borné : petit U-Net à encodeur mobile

Si LR-ASPP manque les traces fines, comparer un **U-Net avec encodeur MobileNetV3**
et décodeur réduit, via `segmentation_models.pytorch` (MIT) et un encodeur dont
la licence/provenance sont vérifiées. Architecture paramétrable, donc aucune
taille universelle annoncée ; compter paramètres, mesurer mémoire et export.
Ne pas multiplier les familles de modèles avant ce comparatif limité.

MobileNetV3-Small seul (~2,54 M paramètres dans sa version classification
TorchVision) peut servir de baseline image/crop, **pas de substitut à une
segmentation**. SAM/LLM multimodal et dépendance GPU obligatoire ne sont pas
nécessaires pour le MVP.

### Licence et reproductibilité

Avant redistribution : distinguer licence du code, conditions des poids
pré-entraînés et droits du corpus. BSD/MIT du code ne garantit pas à elle seule
les droits de tous les poids/datasets. Enregistrer URLs, versions/commits,
notices et hashes ; licence explicite pour nos poids entraînés. Aucun poids
n'a été téléchargé ni modèle installé pendant la rédaction de ce plan.

## 3. Architecture : un socle partagé, pas quatre classes exclusives

Une image peut présenter simultanément nuage, feuillage et traînée. Séparer :

1. **Masques multilabel** : `trail` et `opaque_obstruction` ; masque de voile
   seulement quand une délimitation est réellement justifiable.
2. **Sous-type de chaque trace** : `satellite`, `aircraft`, `unknown`, assorti
   d'une confiance/abstention ; ne pas pénaliser la détection d'une trace lorsque
   seul son sous-type est inconnu.
3. **État global/local du voile** : probabilité calibrée ou score explicitement
   non probabiliste, associé aux indices photométriques. Une transmission
   numérique demeure une mesure de flux relative, pas une invention du réseau.
4. **Qualité et validité** : domaines couverts, modèle/version, incertitude,
   régions non revues/invalides et erreurs séparées.

Commencer par **traînées + obstructions** ; le voile subtil est une deuxième
étape avec comparaison des mêmes étoiles. Évaluer une vue globale réduite pour
le contexte et des tuiles chevauchantes proches de la résolution native pour
les traces fines. Exemples à tester : tuiles 512/768 px, batch 1 sur CPU.
Les tuiles sont fusionnées en coordonnées natives sans artefacts de bord.

Ne pas réduire aveuglément une image 2 MP à 224 px : un trait peut disparaître.
Une cascade qui n'inspecte que les régions proposées doit prouver qu'elle ne
perd pas les traits faibles ; sinon couvrir toutes les tuiles valides.

Entrées : plan scientifique CFA/RGB/mono déclaré, masques invalides et
transformations explicites. L'annotation peut se faire sur l'aperçu étiré,
mais l'entraînement relit l'original avec un prétraitement déterministe,
versionné et identique à l'inférence. Une normalisation locale peut servir à
la morphologie ; conserver séparément les amplitudes/fond/exposition pour le
voile. Ne pas déduire la transparence du seul aperçu auto-étiré.

Pour le contexte temporel futur : coordonnées ciel pour les étoiles et leur
flux, coordonnées détecteur pour les défauts capteur ; tracer les deux mappings.
Ne pas supposer que la caméra est immobile ou que les poses voisines sont
claires. Définir un mode sans voisins et sa fiabilité, pas de référence cachée.

## 4. Boucle utilisateur dans le viewer

Parcours proposé : **Analyser → Visualiser → Annoter/corriger → Enregistrer →
Préparer le corpus → Entraîner un candidat → Comparer → Activer explicitement**.

### ML-01 — Annotation utilisable sans ML

- [ ] Mode « Annoter » distinct de navigation : barre d'outils, raccourcis,
  undo/redo, sélection/édition/suppression d'une annotation.
- [ ] Traînée : polyligne/segment + largeur ; sous-type facultatif/unknown.
- [ ] Obstruction : polygone ou pinceau ; motif facultatif feuillage/bâtiment/autre.
- [ ] Voile : état image ou région, intensité subjective identifiée comme telle,
  possibilité « incertain » ; pas d'obligation de dessiner une frontière fictive.
- [ ] Validation négative **par famille** : « aucune traînée après revue »,
  « pas d'obstruction », etc. Une image non annotée n'est jamais un négatif.
- [ ] Marquer les régions revues/ignorées et annotations partielles ; les zones
  inconnues ne deviennent pas du fond négatif dans la fonction de coût.
- [ ] Afficher séparément prédiction et vérité humaine ; accepter/refuser/corriger
  une proposition sans écraser la provenance originale. Proposition ML ≠ annotation validée.
- [ ] Mode séquence : navigation temporelle, référence voisine ; propagation
  éventuelle proposée, jamais 84 copies automatiquement déclarées validées.
- [ ] Enregistrer localement et rouvrir les annotations, sans modifier les FITS
  ni les décisions de rejet du projet courant.

**Travail Qt concret :** ZeImageView utilise déjà `QGraphicsView/QGraphicsScene`.
Ajouter des items d'overlay et un contrôleur d'annotation séparé, pas une seconde
copie du visualiseur. Transformer souris → scène → pixmap → pixels natifs, y
compris zoom, Fit/1:1, redimensionnement, réduction CFA, flip/orientation et HiDPI.
Associer chaque édition à un identifiant image/token : un chargement asynchrone
ou une sélection rapide ne doit pas enregistrer le dessin sur la mauvaise pose.
En mode annotation, Delete/Backspace supprime l'annotation sélectionnée, **pas
le FITS** (ces touches servent actuellement à `delete_current` dans le viewer).
Préserver le comportement normal hors mode annotation.

**Gate ML-01 :** vrai test Qt dessin → sauvegarde → reload, coordonnées natives
vérifiées à plusieurs zooms/échelles, changement rapide de pose, annulation,
undo/redo et protection des originaux. Fonctionne sans PyTorch/ONNX.

### ML-02 — Corpus et contrats versionnés

- [ ] Étendre par **nouvelle version** les contrats existants
  [corpus v1](corpus-annotation-contract-v1.md) et
  [résultats v1](detection-result-contract-v1.md) : l'enum v1 ne comprend pas
  `obstruction`, ni toutes les géométries/régions de revue requises.
- [ ] Spécifier compatibilité/migration additive, lecteurs anciens, annotations
  image vs pixel, sous-types, masques ignore, identités et validation du schéma.
  Ne pas écrire ces nouveaux champs en les faisant passer pour du v1 conforme.
- [ ] Sidecars/base locale atomiques, versionnés, exportables ; identité stable
  (ID/hash calculé à l'admission si utile) et relocalisation par manifeste local.
  Export portable avec chemins relatifs pseudonymisés, pas chemins personnels.
- [ ] Capturer annotateur/date, provenance manuelle ou modèle proposé/version,
  revue, confiance humaine distincte de confiance machine, révisions/désaccords.
- [ ] Organiser sessions/cibles/événements/instruments ; répartir avant extraction
  des patches. Même original, FITS/PNG dérivé, voisins, mosaïque et augmentations
  restent dans le même split. Préserver la règle existante session/cible entière ;
  utiliser les groupes liés, pas un split aléatoire par fichier.
- [ ] `development` séparé de validation et holdout ; validation/holdout revus
  par un second annotateur conformément au contrat. Ne pas cocher reviewed sur
  une simple seconde lecture par la même personne ou acceptation du modèle.
- [ ] Labels incertains : conservés pour l'abstention, pas forcés en positif ou
  négatif ; tags faibles sans masques ne deviennent pas de faux masques précis.
- [ ] Données et poids hors Git ; manifests/exemples anonymes seulement dans le
  dépôt. Aucun envoi d'images ou télémétrie implicite.

**Corpus de départ connu :** 7 poses de traînées signalées par le propriétaire,
et une séquence de feuillage signalée de 84 poses. Ce sont des pistes à annoter,
pas 91 vérités pixel à pixel déjà qualifiées. Les 84 poses constituent un seul
événement ; leurs témoins propres voisins restent dans le même groupe/split.
Prélever des représentants puis chercher d'autres événements/instruments.

**Dimensionnement progressif, pas quota magique :**

- pilote outil/labels : 100–200 images diverses, dont négatifs difficiles ;
- premier entraînement exploratoire : ordre de grandeur 500–1 000 images
  réellement revues, des dizaines d'événements indépendants ;
- extension : pilotée par courbes d'apprentissage, couverture des cas et bornes
  d'incertitude. 5 000–20 000 images est un scénario possible, **pas une exigence
  démontrée ni une garantie**. Beaucoup de quasi-doublons apportent peu ;
- synthèse : trails à profils/angles/intermittences variés sur fonds réels,
  en respectant le split du fond ; supplément seulement, avec vrai test réel.

### Objectif de collecte pratique — proposition, pas seuil de suffisance

Pour une première bêta **limitée au domaine validé**, viser un corpus total de
l'ordre de **3 000 images annotées**, validation et holdout inclus, par exemple :

| Strate principale de collecte | Ordre de grandeur |
|---|---:|
| Sans ces défauts, dont négatifs difficiles (nébuleuses, colonnes, suivi, Lune) | 1 500 |
| Traînées : satellites, avions et type inconnu, luminosités/angles variés | 500 |
| Obstructions : feuillage, toits/bâtiments et autres régions opaques | 500 |
| Voile probable/nuages : dense, ténu, uniforme, partiel | 500 |

C'est une répartition de collecte indicative, pas une hypothèse de classes
exclusives : conserver tous les labels d'une image présentant plusieurs défauts,
mais ne pas la compter plusieurs fois dans le total d'images uniques. Réserver
validation/holdout par groupes dès le départ ; ces images ne servent pas au
fine-tuning. Ajuster effectifs par catégorie, événements et faux positifs requis.

Pour prétendre à plusieurs instruments/sites, envisager ensuite **5 000–20 000**
images très diverses, à redimensionner selon courbes d'apprentissage et nouveaux
cas d'échec. Aucun nombre brut ne garantit le résultat ; un sous-type rare
comme les avions doit avoir assez d'événements dans chaque split, sinon rester
expérimental/unknown. L'annotation pixel est importante pour les masques : des
tags image seuls ne suffisent pas à valider la localisation.

La suffisance est un verdict de validation : performances par type de défaut et
instrument sur événements non vus, faux positifs bornés, abstention explicite,
courbes d'apprentissage et latence CPU acceptable. N'exiger ni 20 000 images
avant le premier essai ni déclarer le produit fiable au seul passage de 3 000.

### ML-03 — Spike scientifique et export

- [ ] Environnement d'entraînement isolé PyTorch/TorchVision, sans modification
  des dépendances du produit ni du runtime ZeAlfie. Versions épinglées.
- [ ] Baselines satdet réparé et spikes existants conservés ; comparaison
  aveugle sur mêmes données réelles. Aucun résultat PARTIAL passé ne devient
  automatiquement preuve du nouveau modèle.
- [ ] Premier LR-ASPP multi-sorties ; pertes adaptées au déséquilibre des classes
  et aux masques partiels (par exemple BCE/Dice avec ignore), échantillonnage
  incluant négatifs ; ne pas optimiser l'accuracy pixel dominée par le fond.
- [ ] Fine-tuning progressif avec jeux de données figés, seeds, checkpoint,
  journal de versions/configuration/splits et early stopping sur validation.
- [ ] Challenger U-Net seulement si faiblesse mesurée sur traces fines ; pas de
  grosse recherche d'hyperparamètres avant de valider les données.
- [ ] Export ONNX, opset/formes déclarés ; parité PyTorch/ONNX contrôlée sur
  logits, masques et décisions. Mesurer modèle complet et tous les patches.
- [ ] Intégration d'indices photométriques/temps évaluée par ablation ; aucune
  prétention de transmission absolue ou météo certaine.

**Gate :** rappel par événement/trace et géométrie, faux positifs par image,
qualité de masque d'obstruction, abstention, confusions satellite/avion et
performance par contexte. Pour traits fins, distance à l'axe/endpoints/largeur
et tolérance explicitée en plus du Dice/IoU. Pour voile, validation événement
et cohérence avec photométrie ; ne pas utiliser une note purement subjective
comme étalon de transmission.

### ML-04 — Inférence portable et mesurée

**TinyDebian :** CPU en priorité, ONNX Runtime CPU, chargement paresseux,
batch/tile bornés et nombre de threads contrôlé. Machine inspectée le 2026-10-03 :
i7-8550U, 4 cœurs/8 threads, environ 7,5 GiB RAM totale ; RAM disponible variable.
La taille des poids ne justifie aucune promesse de vitesse ou mémoire.

**RTX 3070 Laptop / 3070M (matériel corrigé par Tristan) :** entraînement
PyTorch + CUDA et inférence GPU optionnelle. Architecture Ampere, généralement
8 Go de VRAM ; capacité effectivement disponible à vérifier sur sa machine.
Ce GPU est adapté au fine-tuning des petits modèles proposés, avec tuiles,
batch ajustable, AMP après validation et accumulation de gradients au besoin.
Commencer par un batch de 1 sur tuiles 512 px et mesurer le pic VRAM avant de
l'augmenter ; ce réglage est un point de départ, pas un résultat déjà testé.
Qualifier l'ensemble pilote/PyTorch/CUDA/cuDNN par vrai forward/backward,
export puis parité CPU/GPU. Aucun besoin spécifique Blackwell/CUDA 12.8.
La 3070M n'a pas été testée pendant ce cadrage. L'entraînement d'un modèle
partageable n'impose pas ce matériel aux utilisateurs : inférence CPU portable
par défaut, accélération facultative, pas d'entraînement requis pour utiliser
les poids publiés. La portée scientifique reste limitée aux instruments/formats
réellement validés ; portabilité matérielle ne signifie pas universalité astro.

- [ ] ONNX Runtime GPU en option ; ne pas installer `onnxruntime` et
  `onnxruntime-gpu` concurremment sans politique de packaging claire. Pas de
  TensorRT requis au MVP. Repli CPU visible en cas d'indisponibilité GPU.
- [ ] TinyDebian : annotation et détection normales ; entraînement CPU possible
  pour tests ou tête gelée, mais complet non recommandé et non promis interactif.
- [ ] Sur la 3070M, commencer FP32 de référence puis AMP/FP16 si validé ; INT8 CPU
  seulement après étalonnage et vérification des pertes sur traces faibles.
- [ ] Un service/session d'inférence borné réutilisé, pas un modèle chargé par
  chacun des workers existants ; éviter multiplication des threads/VRAM.
- [ ] Worker hors thread GUI ; progression réelle, annulation entre tuiles,
  reprise explicite, OOM contrôlé, aucune modification du modèle actif en plein run.
- [ ] Mesurer froid/chaud, lecture+prétraitement+tuilage+fusion compris : p50/p95,
  RSS parent/workers, VRAM, débit début/fin, cancellation, lot natif 2 MP.
- [ ] Fixer budgets chiffrés après spike suivant le
  [protocole existant](benchmark-protocol-v1.md), avant promotion. Aucun temps
  par image n'est promis ici à partir du seul nombre de paramètres.
- [ ] CPU disponible Linux/Windows/macOS dans l'ensemble versions supportées ;
  GPU NVIDIA qualifié sur machine réelle. Ne pas revendiquer un OS validé sur
  la seule portabilité théorique d'ONNX.

### ML-05 — Entraîner depuis l'atelier, sans apprentissage silencieux

L'interface pilote un **job**, pas un gradient à chaque coup de souris.

- [ ] Bouton « Préparer/Exporter le corpus » avec compteurs par classe, événements,
  revue et splits ; manifeste figé de chaque entraînement.
- [ ] Bouton « Entraîner un candidat » pour machine équipée ; processus séparé,
  paramètres simples/preset, progression, stop/checkpoint. Export/import manuel
  portable pour entraîner sur le PC 3070M sans service distant obligatoire.
- [ ] Charger ensuite un paquet modèle (ONNX + manifeste + labels + préparation
  + versions/hashes + métriques + licence), pas du code arbitraire/pickle depuis
  le viewer. Vérifier compatibilité avant utilisation.
- [ ] Comparer actif/candidat sur jeu figé ; activation explicite et atomique,
  modèle précédent conservé pour rollback, modèle actif figé pendant un run.
- [ ] Continuer l'entraînement sur corpus équilibré ancien+nouveau, pas seulement
  la dernière correction (oubli catastrophique). Historique reproductible.
- [ ] Proposer à annoter les erreurs, désaccords et cas incertains du pool de
  développement, plus un échantillon aléatoire/diversifié pour éviter le biais
  d'active learning. Ne jamais recycler le holdout final pour améliorer le modèle.

**Gate :** interruption de job sans corruption, inférence inchangée tant que
le candidat n'est pas activé, rollback reproduisant les sorties antérieures,
originaux immuables et annotations accessibles sans runtime ML.

### ML-06 — Promotion expérimentale, puis produit

- [ ] Nuits/cibles/événements de test indépendants ; modèles/prétraitement/seuils
  figés avant holdout, effectifs et intervalles de confiance rapportés.
- [ ] Comparer aux baselines sur rappel/FP/abstention et coût ; validation des
  probabilités/seuils sur validation seulement, ne pas appeler softmax « certitude ».
- [ ] Cibles hors domaine : état indéterminé explicite lorsque conditions non
  couvertes ; la confiance élevée d'un réseau ne garantit pas l'absence d'OOD.
- [ ] Seuils d'acceptation multi-familles fixés avant entraînement long. Les
  objectifs historiques trails ≥95 %/FP ≤1 % restent proposés, pas acquis.
- [ ] Quantifier les négatifs indépendants : 0 FP sur quelques dizaines ne prouve
  pas 1 % ; environ 300 négatifs indépendants sans FP donnent un ordre de grandeur
  de borne supérieure 95 % autour de 1 %, pas si ce sont 300 poses corrélées.
- [ ] Mode « conseil » d'abord : masks/raisons, aucune modification automatique
  des décisions de rejet, du score quality-first, de la référence ou du CSV ZSSS.
- [ ] Toute influence future sur sélection/classement/Stack Plan doit avoir
  politique explicite, migrations/tests du contrat consommateur et accord produit.
- [ ] Modèle optionnel absent/endommagé/incompatible : fonctionnalités historiques
  conservées, état indisponible fidèle, aucun faux négatif « image propre ».

## 5. Découpage conseillé et livrables

| Jalon | Livrable | Condition de passage |
|---|---|---|
| ML-00 | Contrat d'extension annot./résultats et choix du spike | Respect v1, labels multiples, géométries, licence/provenance |
| ML-01 | Annotation manuelle intégrée | Sauvegarde/reload/coordonnées/Qt et sécurité validés sans ML |
| ML-02 | Corpus exportable, splits/revue | Diversité réelle, provenance, pas de fuite ni faux négatifs implicites |
| ML-03 | Candidat LR-ASPP, challenger éventuel, ONNX | Benchmark scientifique + parité export ; go/no-go honnête |
| ML-04 | Inférence CPU/GPU optionnelle | Budget réel TinyDebian, smoke 3070M, GUI fluide |
| ML-05 | Jobs d'entraînement et gestion de modèles | Actif/candidat séparés, rollback, reproductibilité |
| ML-06 | Rapport holdout et mode conseil | Gains démontrés, limites explicites, pas de changement ZSSS implicite |

L'outil d'annotation est utile même si le premier réseau échoue : il fournit
également le corpus manquant pour Hough/MRT et la photométrie explicite.
**Prochaine mission bornée recommandée : ML-00, puis ML-01 ; pas entraîner
immédiatement un modèle sur les seules images déjà signalées.** Aucun planning
calendaire fiable avant de connaître le volume d'annotation et les événements.

## 6. Sources vérifiées pour ce cadrage

Sources upstream lues le 2026-10-03 ; épingler les versions exactes lors du spike.

- [TorchVision LR-ASPP source / métadonnées](https://github.com/pytorch/vision/blob/main/torchvision/models/segmentation/lraspp.py)
- [TorchVision licence BSD-3-Clause](https://github.com/pytorch/vision/blob/main/LICENSE)
- [MobileNetV3 référence](https://github.com/pytorch/vision/blob/main/torchvision/models/mobilenetv3.py)
- [Segmentation Models PyTorch](https://github.com/qubvel-org/segmentation_models.pytorch)
- [ONNX Runtime execution providers CPU/CUDA](https://onnxruntime.ai/docs/execution-providers/)

Recherche documentaire et inspection du viewer uniquement : **aucun modèle
astronomique déjà entraîné fourni, aucun benchmark ML, aucune nouvelle
installation, aucun changement des contrats v1 ou du code produit dans ce plan.**
