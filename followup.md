# followup.md - V‚rifs et checklist (splitter vertical)

## Checklist code
- [x] Modifs limit‚es … `zeviewer.py`.
- [x] Toolbar hors splitter (inchang‚e).
- [x] `self.vsplitter` cr‚‚ en `Qt.Vertical`, `childrenCollapsible=False`.
- [x] Le bas est regroup‚ dans `self.hist_container` (un seul widget ajout‚ au splitter).
- [x] `setStretchFactor(0,4)` et `setStretchFactor(1,1)` (ou ‚quivalent).
- [x] `hist_container` a un `minimumHeight` pour ‚viter qu'il disparaisse.
- [x] Aucun changement aux signaux/slots histogramme/stretch.

## Tests manuels
- Ouvrir FITS  image non ‚cras‚e, header affich‚, histogramme OK.
- Drag splitter vertical  haut/bas se redimensionnent.
- Resize fenˆtre  layout stable.
- Next/Prev  tout se met … jour normalement.
- Clear  vide image + header, histogramme reste conforme.

## Sanity
- [x] `python -m compileall zeviewer.py`
