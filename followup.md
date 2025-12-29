# followup.md

## Checklist de vérification (manuelle)
1) [ ] Lancer l'app Qt.
2) [ ] Dans Project, choisir un dossier A contenant `stack_plan.csv` :
   - [ ] Aller sur l'onglet Stack plan -> doit afficher les lignes.
   - [ ] Vérifier log : `stack_plan_autoload_loaded`.
3) [ ] Toujours sur Stack plan, changer Project vers dossier B sans `stack_plan.csv` :
   - [ ] Table vide.
   - [ ] Log : `stack_plan_autoload_missing`.
4) [ ] Dans Results (après une analyse), cliquer "Créer plan de stack" :
   - [ ] Vérifier que `Project/stack_plan.csv` est créé.
   - [ ] Revenir Stack plan : le plan est bien affiché.
5) [ ] Cliquer "Exporter le plan en CSV" :
   - [ ] "Save as." s'ouvre dans le Project.
   - [ ] Fichier écrit.
6) [ ] Cliquer "Préparer le script d'empilage" :
   - [ ] "Save as." s'ouvre dans le Project.
   - [ ] Script écrit, et sur Linux/macOS il est chmod +x (best-effort).

## Vérifs anti-régression
- [ ] Preview autoload : sélectionner un Project avec images, aller sur Preview -> autoload inchangé.
- [ ] Pas de scan lourd : vérifier qu'aucun `os.walk(project_dir)` n'a été ajouté dans le code stack plan.
- [ ] Multi-OS : aucun chemin hardcodé, uniquement `os.path.join/abspath`.

## Tests rapides (optionnel, sans UI)
Dans un python shell :
- [ ] Créer un CSV minimal `stack_plan.csv` (header + 2 lignes) dans un dossier temp.
- [ ] Instancier `StackPlanModel(path)` et vérifier `rowCount()==2`.

## Deliverables attendus (git)
- Diff sur `analyse_gui_qt.py` + `zone.py`
- Commit message suggéré :
  - "Stack Plan: autoload from Project stack_plan.csv + export/script actions"
