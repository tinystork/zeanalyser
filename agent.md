# agent.md — ZeViewer: Histogramme plein écran + poignées + balance RVB (anti-vert)

## Objectif
Améliorer l’onglet Preview (ZeViewer) pour obtenir :
1) Un histogramme **plein largeur** (lisible), qui se redimensionne avec la fenêtre.
2) Deux **poignées/barres** (black point / white point) **draggables** sur l’histogramme, reliées aux spinboxes (min/max) et au stretch.
3) Une **balance RVB automatique** (preview-only) pour éviter le rendu “tout vert” sur les FITS couleur (mosaïques / RGB).

## Non-objectifs (ne pas faire)
- Ne pas modifier le pipeline d’analyse ZeAnalyser (onglets Analyzer/Results/Organizer/etc.).
- Ne pas ajouter de dépendances (pas de matplotlib, pas de nouveaux packages).
- Ne pas toucher au backend matplotlib / env MPLBACKEND.
- Ne pas créer de nouvelle UI complexe (pas de menu settings, pas de persistance disque).

## Scope verrouillé
- **Un seul fichier modifié : `zeviewer.py`**
- Aucune modification de `analyse_gui_qt.py` (il instancie déjà `ZeViewerWidget`).
- Conserver l’API publique de `ZeViewerWidget` (au minimum `load_path()`, `apply_stretch()`, `clear()`, `go_prev/go_next/delete_current`, `retranslate_ui()`).

## Contexte technique actuel (à respecter)
- Chargement asynchrone via `PreviewLoadRunnable` et `QThreadPool` limité à 1 thread.
- `apply_stretch()` convertit un tableau numpy vers `QImage` et l’affiche.
- L’histogramme est actuellement rendu dans un `QLabel` avec un pixmap de largeur = nb bins, ce qui le rend minuscule.
- La sécurité mémoire QImage doit être stricte : `np.ascontiguousarray(...)` + `QImage(...).copy()`.

---

## Plan d’implémentation

### [x] 1) Remplacer l’affichage histogramme par un widget custom (plein largeur)
Créer une classe Qt `ZeHistogramWidget(QWidget)` (dans le bloc `else:` quand Qt est dispo) :
- Propriétés internes :
  - `self._hist` (dict `{counts, edges, channels}`)
  - `self._lo`, `self._hi` (niveaux courants)
  - `self._drag_handle` ∈ {"lo","hi",None}
- Signaux :
  - `sig_levels_changing = Signal(float, float)` (émis pendant drag, throttlé côté parent)
  - `sig_levels_changed = Signal(float, float)` (émis au mouseRelease)
- Rendu :
  - `paintEvent()` dessine :
    - fond sombre
    - histogramme RGB si `counts` shape=(3,bins), sinon mono
    - barres verticales lo/hi (couleur distincte)
  - IMPORTANT : dessiner à la taille réelle du widget (`self.rect()`), donc histogramme “plein écran” horizontal.
- Interaction :
  - `mousePressEvent`: sélectionner la poignée la plus proche (lo/hi) si click à ±N pixels d’une barre, sinon sélectionner la plus proche par distance.
  - `mouseMoveEvent`: convertir `x` -> valeur data via `edges[0]..edges[-1]`, clamp, maintenir `lo < hi` (avec epsilon).
  - `mouseReleaseEvent`: fin drag, émettre `sig_levels_changed`.

UI :
- Dans `_build_ui()` : remplacer `self.hist_label = QLabel("")` par `self.hist_widget = ZeHistogramWidget()`
- `SizePolicy` : `Expanding` en largeur, `Minimum` en hauteur, et min height ~ 120.

### [x] 2) Synchronisation poignées <-> spinboxes <-> stretch (avec garde anti-récursion)
Dans `ZeViewerWidget` :
- Ajouter champs :
  - `self._levels_sync_guard = False`
  - `self._pending_levels = None`
  - `self._levels_timer = QTimer(...)` (ou `QTimer.singleShot` pattern), interval ~ 30–50ms
- Connexions :
  - `hist_widget.sig_levels_changing.connect(self._on_hist_levels_changing)`
  - `hist_widget.sig_levels_changed.connect(self._on_hist_levels_changed_final)`
- Implémenter :
  - `_on_hist_levels_changing(lo,hi)` :
    - Met à jour les spinboxes (sans boucler) : si `_levels_sync_guard` -> ignore
    - Stocker `self._pending_levels=(lo,hi)` et démarrer timer si pas actif
  - Timer callback :
    - Si `pending_levels` existe : appeler `apply_stretch(lo,hi)` (au plus 20–30 fps)
  - `_on_hist_levels_changed_final(lo,hi)` :
    - Appliquer immédiatement `apply_stretch(lo,hi)` (et effacer pending)
- Quand `apply_stretch()` est appelé (par bouton, auto-level, etc.) :
  - Mettre à jour l’histogramme : `hist_widget.set_levels(lo,hi)` + `update()`

⚠️ Verrou : aucune récursion infinie (guard obligatoire).
- Utiliser `self._levels_sync_guard=True` pendant `spinbox.setValue(...)`.
- Ne pas connecter `valueChanged` des spinboxes pour l’instant (on garde “Apply stretch” + drag handles).

### [x] 3) Corriger le rendu “vert” par une auto white-balance preview-only
Implémenter une balance “gray-world” **dans le worker preview** (pas dans l’analyse) :
- Ajouter une fonction pure helper (en bas du fichier, côté helpers) :
  - `_compute_gray_world_gains_rgb(arr_rgb, sample_max=200000) -> (gains_rgb_tuple, medians_tuple)`
    - Échantillonner des pixels (pas flatten channels mélangés) :
      - Sélectionner un sous-échantillonnage régulier sur (H,W) pour limiter à ~sample_max pixels.
      - Pour chaque canal, prendre `median` des valeurs finies.
    - Gains :
      - cible = median_G (ou median moyenne des 3)
      - gain_R = cible / median_R, gain_G = 1.0, gain_B = cible / median_B
      - clamp gains, ex : [0.25, 4.0] (éviter délire si median quasi 0)
      - si median_R/B invalides (nan, <=0), fallback gain=1.
- Dans `PreviewLoadRunnable.run()` :
  - Après `linear = self._load_image(...)` :
    - si `linear.ndim==3 and linear.shape[2]==3` :
      - calculer gains
      - `balanced = linear * gains` (broadcast float32)
      - Utiliser `balanced` pour :
        - `hist_sample`, `stats`, `hist`, `auto_lo/auto_hi`
      - Mettre dans payload :
        - `payload["linear_ds"] = balanced` (utilisé pour display)
        - `payload["wb_gains"] = gains`
    - sinon : garder comportement actuel.
- Dans `ZeViewerWidget._on_worker_result()` :
  - stocker `self._wb_gains = payload.get("wb_gains")`
  - `self._linear_ds = payload["linear_ds"]` (donc déjà équilibrée si RGB)
  - IMPORTANT : stats/hist/auto doivent correspondre à `linear_ds` affichée.

### [x] 4) Sécurité mémoire QImage (MUST)
Dans `apply_stretch()` :
- Avant création `QImage`, forcer `disp = np.ascontiguousarray(disp)`
- Conserver `QImage(...).copy()` (déjà présent).
- Idem grayscale : contigu + copy.

### [x] 5) Compat et robustesse
- Le mode headless / Qt absent doit continuer à importer sans crash :
  - Si besoin, définir un dummy `ZeHistogramWidget` (no-op) dans la branche `if not QT_AVAILABLE or np is None`.
- Ne pas changer la logique de tri existante (stable sort déjà ok).
- Ne pas modifier la logique navigation/suppression.

---

## Critères d’acceptation (Definition of Done)
1) L’histogramme occupe **toute la largeur disponible** et reste lisible après resize.
2) Deux barres lo/hi sont visibles et **draggables** à la souris.
3) Pendant le drag : l’image se met à jour (throttlée) et les spinboxes reflètent les valeurs.
4) Le rendu “vert” est **fortement réduit** sur FITS couleur (RGB) via auto WB preview-only.
5) Aucune régression :
   - Navigation left/right, touches clavier, delete confirm intact
   - Open file dialog démarre dans le bon dossier
   - Import headless ne casse pas
6) Pas de dépendances ajoutées, pas de modifications hors `zeviewer.py`.

---

## Notes d’implémentation (détails attendus)
- Couleurs histogramme : rester simple (RGB) ; pas besoin d’axes numériques pour ce patch.
- Epsilon pour lo/hi : ex `eps = 1e-9 * max(1, abs(hi-lo))` ou petit constant.
- Conversion position -> valeur :
  - utiliser `edges[0]..edges[-1]` pour mapping linéaire
  - clamp aux bornes
- Performances : timer 30–50ms, ne pas recalculer histogramme pendant drag (juste redraw barres + apply stretch).
