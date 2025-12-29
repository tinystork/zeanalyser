# agent.md - ZeViewer Preview: ajouter un QSplitter VERTICAL (haut vs histogramme)

## Objectif
Dans `zeviewer.py`, dans l'onglet Preview, ajouter un **QSplitter vertical** entre :
- **Bloc haut** : preview (QSplitter horizontal image + header)
- **Bloc bas** : histogramme + contr“les stretch + stats

But : ‚viter que l'image soit "r‚tatin‚e" et permettre un redimensionnement vertical naturel (comme sur la capture).

## Contraintes anti-r‚gression
- Scope strict : **zeviewer.py uniquement**.
- Ne pas toucher … la logique de chargement, navigation, suppression, histogramme, stretch, autoload.
- Ne pas ajouter de styles/couleurs hardcod‚s (le thŠme/skin pilote).
- Pas de freeze UI : aucune nouvelle lecture disque c“t‚ thread UI.
- Garder le threadpool viewer d‚di‚ tel quel (1 thread), ne pas toucher au global.

## Design attendu
- La toolbar (boutons Prev/Next/Delete/Open/Fit/Zoom/Reset/Clear) reste **hors splitter** (en haut, fixe).
- Juste en dessous : `QSplitter(Qt.Vertical)` :
  - Widget 0 (haut) : le splitter horizontal existant (image+header)
  - Widget 1 (bas) : le panneau histogramme/stretch existant

## Impl‚mentation (‚tapes pr‚cises)

### 1) Imports
Ajouter dans les imports PySide6 (si pas d‚j…) :
- `QSplitter`
- `QWidget`
- `QVBoxLayout`
- `QSizePolicy` (si tu dois ajuster les policies)

### 2) Regrouper le bas (histogramme) dans un conteneur unique
Dans `ZeViewerWidget._build_ui()` :
- Cr‚er `self.hist_container = QWidget()`
- Mettre **tout ce qui est histogramme + stats + stretch controls** dans un `QVBoxLayout(self.hist_container)`
  - IMPORTANT : tu ne changes pas les widgets, tu les **d‚places** dans ce layout.

Astuce : si aujourd'hui tu ajoutes au layout principal des ‚l‚ments du bas via `layout.addWidget(...)`,
remplace-les par `hist_layout.addWidget(...)`.

### 3) Ajouter le QSplitter vertical
Toujours dans `_build_ui()` :
- Tu as d‚j… un splitter horizontal (souvent `self.splitter` ou `self.hsplitter`) contenant `image_view` et `header_view`.
- Cr‚er :
  - `self.vsplitter = QSplitter(Qt.Vertical)`
  - `self.vsplitter.setChildrenCollapsible(False)`

Puis :
- `self.vsplitter.addWidget(self.splitter)`   # le splitter horizontal existant (image+header)
- `self.vsplitter.addWidget(self.hist_container)`

Et dans le layout principal :
- Remplacer l'ajout direct de `self.splitter` + histogram widgets par **un seul** `layout.addWidget(self.vsplitter)`.

### 4) Taille initiale + policies (pour ‚viter l'‚crasement)
R‚glages recommand‚s :
- `self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)`
- `self.vsplitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)`
- Donner une hauteur minimale raisonnable au bas :
  - `self.hist_container.setMinimumHeight(220)` (ou 250 selon ton UI)
- Priorit‚ au haut :
  - `self.vsplitter.setStretchFactor(0, 4)`
  - `self.vsplitter.setStretchFactor(1, 1)`
- (optionnel mais efficace) tailles initiales :
  - `self.vsplitter.setSizes([700, 300])`
    (valeurs "safe", Qt adaptera selon la taille de fenˆtre)

### 5) Ne pas casser les hooks existants
- Ne change pas les noms/refs des widgets histogramme existants (canvas, controls, labels).
- Ne change pas les connexions signals/slots.
- Juste du **re-layouting**.

## CritŠres d'acceptation
- [x] L'image n'est plus ‚cras‚e verticalement … l'ouverture (elle a de la hauteur).
- [x] Un handle de splitter vertical apparaŒt entre le bloc haut et l'histogramme, redimensionnable.
- [x] Le comportement histogramme/stretch/stats est inchang‚.
- [x] Le thŠme/skin est respect‚ (pas de fond blanc impos‚).
- [x] Aucun lag/freeze suppl‚mentaire.

## Tests manuels
1) Ouvrir un FITS : image + header OK, histogramme OK.
2) Redimensionner la fenˆtre : le bloc haut grandit/r‚tr‚cit correctement.
3) Drag du handle vertical : le ratio haut/bas change en live.
4) Next/Prev : tout reste coh‚rent.
5) Clear : comportement inchang‚.
