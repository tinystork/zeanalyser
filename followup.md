# followup.md — Vérifs et checklist (splitter vertical)

## Checklist code
- [ ] Modifs limitées à `zeviewer.py`.
- [ ] Toolbar hors splitter (inchangée).
- [ ] `self.vsplitter` créé en `Qt.Vertical`, `childrenCollapsible=False`.
- [ ] Le bas est regroupé dans `self.hist_container` (un seul widget ajouté au splitter).
- [ ] `setStretchFactor(0,4)` et `setStretchFactor(1,1)` (ou équivalent).
- [ ] `hist_container` a un `minimumHeight` pour éviter qu’il disparaisse.
- [ ] Aucun changement aux signaux/slots histogramme/stretch.

## Tests manuels
- Ouvrir FITS → image non écrasée, header affiché, histogramme OK.
- Drag splitter vertical → haut/bas se redimensionnent.
- Resize fenêtre → layout stable.
- Next/Prev → tout se met à jour normalement.
- Clear → vide image + header, histogramme reste conforme.

## Sanity
- `python -m compileall zeviewer.py`
