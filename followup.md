# followup.md — QA & vérifications ZeViewer histogram handles + anti-vert

## Checklist de QA manuelle (Windows / Linux / macOS)
### [ ] A) Histogramme plein écran
1. Lancer ZeAnalyser Qt.
2. Onglet Preview → Open file → sélectionner un FITS (mono + RGB si possible).
3. Vérifier :
   - l’histogramme remplit la largeur
   - pas de “petit histogramme collé à gauche”
4. Redimensionner la fenêtre :
   - l’histogramme se redessine et reste plein écran.

### [ ] B) Poignées / barres lo-hi (black/white points)
1. Charger une image, observer les deux barres verticales sur l’histogramme.
2. Drag la barre “lo” vers la droite :
   - l’image se renforce en contraste (noirs plus denses)
   - le spinbox min change
3. Drag la barre “hi” vers la gauche :
   - hautes lumières plus compressées
   - le spinbox max change
4. Vérifier que lo ne peut pas dépasser hi (clamp correct).
5. Lâcher la souris :
   - l’état final est appliqué
   - pas de freeze / pas de lag cumulatif

### [ ] C) Anti-vert (auto white-balance preview-only)
1. Charger un FITS couleur (mosaïque / RGB).
2. Comparer avant/après :
   - le rendu ne doit plus être “tout vert”
   - un fond neutre doit apparaître (ou au minimum beaucoup moins vert)
3. Vérifier que la balance ne s’applique pas aux images mono (aucun changement).

### [ ] D) Zéro régression navigation / delete
1. Dans un dossier avec plusieurs images :
   - boutons Previous/Next ok
   - touches gauche/droite ok
2. Delete :
   - confirmation Yes/No ok
   - checkbox “don’t show again this session” ok
3. Après suppression :
   - on passe à l’image suivante (ou clear si plus d’images)

### [ ] E) Pas de régression “Open file” dossier
1. Ouvrir une image dans un dossier A.
2. Ouvrir une image dans un dossier B.
3. Cliquer Open file à nouveau :
   - le dialog doit démarrer dans B (dernier dossier utilisé / current image dir).

---

## Vérifications techniques rapides (sanity)
- [x] L’import de `zeviewer.py` ne doit pas casser si PySide6 absent (headless fallback).
- [x] `apply_stretch()` doit utiliser `np.ascontiguousarray(...)` + `QImage(...).copy()` pour éviter crash/artefacts.
- [x] Aucun changement de threadpool (toujours 1 thread dédié preview).
- [x] Pas de dépendances additionnelles.

---

## Signaux d’alerte (à corriger si observés)
- Histogramme flou / pixellisé excessif : vérifier le `paintEvent()` (dessin vectoriel simple, pas de scaling pixmap).
- Drag qui “rame” : réduire fréquence d’apply via timer (50ms), ou n’appliquer que sur release.
- Image toujours très verte :
  - clamp gains trop faible
  - médianes calculées sur mauvais échantillon
  - data pas RGB (ordre des canaux) → si suspicion, log optionnel via env `ZE_VIEWER_DEBUG`.

---

## “Done” final
- Commit unique : “ZeViewer: resizable histogram + draggable levels + preview white balance”
- Fichier modifié : `zeviewer.py` uniquement

