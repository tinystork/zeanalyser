# followup.md — Checklist & test lot massif (Organizer)

## Test rapide (6 fichiers)
- [ ] Créer un dossier avec FITS :
  - 2x EQMODE=1 FILTER=IRCUT
  - 2x EQMODE=0 FILTER=LP
  - 1x EQMODE absent FILTER=IRCUT
  - 1x header cassé / FILTER absent

- [ ] Onglet Organizer → Scan/Preview (dry run ON)
  - Vérifier summary :
    - EQ: IRCUT=2
    - ALTZ: LP=2
    - NO_EQMODE: IRCUT=1
    - erreurs header = 1 (ou UNKNOWN_FILTER selon le cas)

- [ ] Dry run OFF → Apply (Move)
  - Vérifier arborescence `_organized` correcte
  - Vérifier collisions (si tu dupliques les noms) : suffixes __01 etc

## Test lot réel (20 000 FITS)
- [ ] Destination : `<input_dir>/_organized`
- [ ] Include subfolders : ON si l'arbre est profond
- [ ] Skip already organized : ON
- [ ] Scan (dry run ON) : vérifier counts
- [ ] Apply (Move)

Attendus :
- Pas d'explosion RAM (header only)
- Progress régulier
- Cancel fonctionne sans crash

## Après Move : avertissement utilisateur
- [x] Revenir onglet Project et choisir `_organized` comme dossier pour les analyses futures
- [x] Si des résultats d'analyse étaient ouverts avant : relancer une analyse (chemins obsolètes)

## Si beaucoup de UNKNOWN_FILTER
- [ ] Vérifier que le keyword est bien `FILTER` partout
- [ ] Sinon, étendre (optionnel) read_seestar_tags pour fallback sur un second keyword
  MAIS ne le faire que si nécessaire (éviter régression).

---
### Clé de traduction pour le message d’avertissement post-Apply
Comme dit plus haut, ajouter une clé dans la section i18n :

organizer_paths_moved_warning

Et une phrase :

Après un APPLY réussi, afficher zone._("organizer_paths_moved_warning") dans une boîte de dialogue d’information (et ne pas modifier automatiquement le project path).
