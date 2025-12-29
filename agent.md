# agent.md

## Goal
Dans le GUI PySide6 (`analyse_gui_qt.py`), faire en sorte que :
- Le bouton "Create stacking plan" (onglet Project) ouvre la fenêtre de sélection/tri (comme Tk).
- Le bouton "Prepare stacking script" (onglet Stack Plan) utilise EXACTEMENT le même flux : si aucun `stack_plan.csv` n’existe, ouvrir cette fenêtre, puis seulement ensuite préparer le script.
- Ne PAS réutiliser de code Tkinter (copier le comportement en Qt uniquement). Tkinter restera inchangé.

## Scope (STRICT)
- Modifier uniquement `analyse_gui_qt.py`.
- Optionnel : si une clé de traduction manque et casse l’UI, ajouter la/les clés manquantes dans le fichier de traductions existant (uniquement si nécessaire).
- Ne pas modifier `analyse_gui.py` (Tk).
- Ne pas modifier `stack_plan.py`.

## Current bug / Why
- `open_stack_plan_window()` contient déjà la fenêtre de sélection (critères + tri + aperçu + génération CSV).
- Mais le bouton "Create stacking plan" appelle `_create_stack_plan()` (génération directe sans UI).
- Et "Prepare stacking script" fallback appelle aussi `_create_stack_plan()`.
=> Résultat : aucune fenêtre de sélection n’apparaît en Qt.

## Required changes

- [x] A) Brancher "Create stacking plan" sur la fenêtre Qt
  - Localiser le connect du bouton `create_stack_plan_btn.clicked.connect(...)`
  - Remplacer la cible par `self.open_stack_plan_window` (ou wrapper dédié), afin d’ouvrir la fenêtre.

- [x] B) Faire retourner un chemin par `open_stack_plan_window()`
  - Modifier `open_stack_plan_window()` pour retourner `csv_path` si l’utilisateur clique "Générer le plan" (dialog accepté),
    et retourner `None` si l’utilisateur annule/ferme.
  - Implementation recommandée :
    - Déclarer `created_path = None` dans `open_stack_plan_window()`.
    - Dans `generate_plan()`, après écriture CSV, faire `created_path = csv_path`, puis `dialog.accept()`.
    - Après `dialog.exec()`, retourner `created_path`.

- [x] C) "Prepare stacking script" doit utiliser le même flux
  - Dans `_on_prepare_stacking_script_clicked()` :
    - Si `stack_plan.csv` n’existe pas :
      - Appeler `created = self.open_stack_plan_window()`
      - Si `created` est None ou fichier absent => afficher warning et STOP.
      - Sinon utiliser `created` comme `stack_plan_path`.
    - Ensuite continuer le flux existant (load table, SaveAs script, `_prepare_stacking_script(dest_path)`).

- [x] D) Checkbox "Inclure le temps de pose dans le batch" (matching Tk)
  - Ajouter dans la fenêtre `open_stack_plan_window()` une QCheckBox :
    - label: clé trad `include_exposure_in_batch` (ou fallback FR/EN si pas de clé)
    - default: unchecked
    - connecter `stateChanged` à `update_preview()`
  - Dans `update_preview()` et `generate_plan()` passer :
    `include_exposure_in_batch=include_exposure_cb.isChecked()`
    à `stack_plan.generate_stacking_plan(...)`.

## Non-regression constraints
- Ne pas casser le flux "Analyze and Stack" : il peut continuer à utiliser `_create_simple_stack_plan()` (auto) sans ouvrir de fenêtre.
- Ne pas changer le format CSV ni les colonnes.
- Ne pas introduire de dépendances.
- Comportement multi-OS : Windows/Mac/Linux.

## Acceptance tests (manual)
- [ ] Après une analyse (résultats présents), cliquer "Create stacking plan" (Project) :
  - La fenêtre de sélection apparaît.
  - Modifier des critères/tri met à jour "Images sélectionnées" + "Nombre de batchs".
  - Cliquer "Générer le plan" crée `stack_plan.csv` (project dir si possible, sinon log dir, sinon cwd) et remplit l’onglet Stack Plan.

- [ ] Cliquer "Prepare stacking script" (Stack Plan) :
  - Si `stack_plan.csv` existe : propose SaveAs script puis écrit le script.
  - Si `stack_plan.csv` n’existe pas : ouvre la fenêtre de sélection, et si l’utilisateur génère le plan, alors propose SaveAs script.

- [ ] Annuler la fenêtre :
  - Aucun fichier n’est créé.
  - Aucun script n’est généré.

### CRITIQUE — préserver RA/DEC (compat ZeMosaic)
- Le fichier `stack_plan.csv` DOIT continuer d’inclure les colonnes `ra` et `dec` (headers exacts: `ra`, `dec`).
- Ces colonnes doivent être écrites dans TOUS les chemins de génération/export du plan (Create stack plan, Prepare stacking script fallback, génération via la fenêtre).
- Interdiction de “rebuild” un CSV manuellement sans `ra/dec`. Utiliser le writer existant (ou respecter exactement son header/order).
- Si un `stack_plan.csv` legacy sans `ra/dec` est chargé, le modèle UI doit rester robuste (valeurs vides), mais lors d’un nouvel export/génération, `ra/dec` doivent être présents.
