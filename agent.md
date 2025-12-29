# agent.md

## Mission
Rendre l’onglet **Stack plan** utile et non redondant :
1) [x] Il devient une **visionneuse automatique** du fichier `stack_plan.csv` situé **dans le dossier Project** (celui pointé par `input_path_edit`).
2) [x] Le bouton **Prepare stacking script** n’est plus “dummy” : il est **branché au Project** et génère un script sur disque (dans le dossier Project par défaut), basé sur le plan actuellement chargé (ou généré si absent).
3) [x] Bonus low-risk : le bouton **Export plan as CSV** ouvre un “Save as…” (au lieu de juste retourner un string en interne).

## Contrainte clé (anti-régression)
- Ne pas modifier le comportement des autres onglets (Preview, Results, Organizer).
- Ne pas toucher au backend matplotlib, ni au viewer (zeviewer), ni aux workflows lourds d’analyse/organize.
- Aucun scan de répertoire “images” ici : on ne fait que **tester l’existence** de `stack_plan.csv` dans le Project et le lire.
- Tout doit être **multi-OS** (Windows/macOS/Linux) : chemins via `os.path`, pas de commandes shell imposées.

## Scope (fichiers autorisés)
- ✅ `analyse_gui_qt.py` (principal)
- ✅ `zone.py` (ajout de quelques clés i18n minimales)
- 🚫 Ne pas toucher aux autres modules sauf nécessité absolue.

---

## Détails fonctionnels attendus

### [x] A. Source de vérité : `Project/stack_plan.csv`
- Le chemin canonique du plan devient :
  - `stack_plan_path = os.path.join(project_dir_abs, "stack_plan.csv")`
- Si `project_dir` est vide/invalide : l’onglet Stack plan reste vide (pas d’erreur bloquante).

### [x] B. Auto-load du plan (visionneuse)
Déclencheurs :
1) Quand l’utilisateur **active l’onglet Stack plan**.
2) Quand l’utilisateur **change le dossier Project** alors qu’il est déjà sur l’onglet Stack plan.

Comportement :
- Si `Project/stack_plan.csv` existe :
  - Charger le CSV dans la table via `self.set_stack_plan_rows(stack_plan_path)` (en passant **le path str** pour que `StackPlanModel` lise le fichier).
  - Mémoriser `self._stack_plan_loaded_path` + `self._stack_plan_loaded_mtime` pour éviter les reloads inutiles.
- Si le fichier n’existe pas :
  - Afficher table vide via `self.set_stack_plan_rows([])` (ou reset modèle)
  - Log/status via une clé i18n dédiée (voir section i18n).

Protection “freeze” low-cost :
- Avant de charger le CSV : si `os.path.getsize(path) > 100*1024*1024` (100 MB), **ne pas charger** (table vide) + log “fichier trop gros”.

### [x] C. Génération du plan : écrire dans le Project
Modifier tous les endroits Qt qui écrivent `stack_plan.csv` dans le dossier du log :
- `_create_stack_plan()`
- `open_stack_plan_window().generate_plan()`
- `_create_simple_stack_plan()` (workflow auto)
=> Ils doivent écrire en priorité dans `Project/stack_plan.csv` si Project valide, sinon fallback sur ancien comportement (dossier du log), sinon `./stack_plan.csv`.

Après écriture, **recharger depuis le chemin** (pas depuis `plan_rows`) :
- `self.set_stack_plan_rows(stack_plan_path)`
- `self._last_stack_plan_path = stack_plan_path`
- (optionnel) mettre à jour `self._stack_plan_loaded_path/_mtime` pour éviter reload.

### [x] D. Bouton "Prepare stacking script" branché Project
Remplacer le slot direct vers `_prepare_stacking_script` par un handler UI :
- `def _on_prepare_stacking_script_clicked(self): ...`

Comportement :
1) Déterminer `project_dir_abs`.
   - Si invalide -> `QMessageBox.warning(..., _("msg_warning"), _("msg_input_dir_invalid"))` et stop.
2) S’assurer que `Project/stack_plan.csv` existe :
   - S’il existe : OK.
   - S’il n’existe pas : tenter de le générer depuis les résultats en mémoire (même logique que `_create_stack_plan` : `status=="ok"` & `action=="kept"`).
     - Si pas de résultats -> warning via `_('stack_plan_alert_no_analysis')` ou `_('msg_export_no_images')`.
3) Proposer un “Save as…” pour le script :
   - Dossier par défaut : Project
   - Nom par défaut :
     - Windows : `prepare_stacking_script.bat`
     - Autres : `prepare_stacking_script.sh`
4) Générer le script via backend existant `_prepare_stacking_script(dest_path=chosen_path)`.
   - Avant de générer, s’assurer que le modèle stack plan est chargé (si besoin `self.set_stack_plan_rows(stack_plan_csv_path)`).
   - Sur *nix : best-effort `chmod +x`.
5) Message info/log i18n : “script écrit : {path}”.

Important :
- On ne “lance” pas de stacking réel ici (on reste non destructif).
- Le script reste un **preview** (echo des fichiers) comme aujourd’hui, mais enfin utile et basé sur le plan du Project.

### [x] E. Bouton "Export plan as CSV" (bonus utile)
Actuellement `_export_stack_plan_csv()` écrit si `dest_path` est fourni, sinon retourne du texte.
Brancher le bouton vers un handler UI :
- `def _on_export_stack_plan_clicked(self): ...`
Qui :
- Ouvre `QFileDialog.getSaveFileName` par défaut dans Project
- appelle `_export_stack_plan_csv(dest_path=...)`
- log/info i18n “export ok: {path}” / “export failed”.

---

## i18n (zone.py) [x]
Ajouter au minimum ces clés FR+EN :

FR:
- `stack_plan_autoload_loaded`: "Plan chargé depuis : {path}"
- `stack_plan_autoload_missing`: "Aucun stack_plan.csv dans le dossier projet."
- `stack_plan_autoload_too_large`: "stack_plan.csv trop volumineux, chargement ignoré."
- `stack_plan_script_saved`: "Script d'empilage écrit : {path}"
- `stack_plan_script_failed`: "Échec écriture script : {e}"
- `stack_plan_export_saved`: "Plan exporté : {path}"
- `stack_plan_export_failed`: "Échec export plan : {e}"

EN:
- `stack_plan_autoload_loaded`: "Plan loaded from: {path}"
- `stack_plan_autoload_missing`: "No stack_plan.csv found in project folder."
- `stack_plan_autoload_too_large`: "stack_plan.csv too large, loading skipped."
- `stack_plan_script_saved`: "Stacking script written: {path}"
- `stack_plan_script_failed`: "Failed to write script: {e}"
- `stack_plan_export_saved`: "Plan exported: {path}"
- `stack_plan_export_failed`: "Failed to export plan: {e}"

Utiliser `self._log(...)` pour journaliser + éventuellement `QMessageBox.information` pour les actions utilisateur (export/script).

---

## Implémentation (étapes codées)

### 1) analyse_gui_qt.py : indices d’onglets
- [x] Après création de `self.stack_tab_index`, stocker `self._stack_tab_index = self.stack_tab_index`
- [x] Conserver `self._preview_tab_index` existant.

### 2) analyse_gui_qt.py : hook tab change
- [x] Étendre `def _on_main_tab_changed(self, idx)` :
  - [x] Conserver la partie Preview inchangée.
  - [x] Ajouter une branche “Stack tab” :
    - [x] Si `current_idx == self._stack_tab_index` :
      - [x] récupérer `project_dir_abs`
      - [x] `QTimer.singleShot(0, lambda: self._maybe_autoload_stack_plan(project_dir_abs))`

### 3) analyse_gui_qt.py : hook project path changed
- [x] Dans le wiring (déjà existant pour analyse/organizer), ajouter `self.input_path_edit.textChanged.connect(self._on_project_dir_changed)`
- [x] Implémenter : si onglet courant == stack tab => `QTimer.singleShot(0, ...)` vers autoload.

### 4) analyse_gui_qt.py : autoload helper
- [x] Créer `_get_project_dir_abs() -> str`
- [x] Créer `_get_project_stack_plan_path(project_dir_abs) -> str`
- [x] Créer `_maybe_autoload_stack_plan(project_dir_abs: str) -> None` avec cache mtime + file size guard.

### 5) analyse_gui_qt.py : écrire le plan dans Project
- [x] Modifier `_create_stack_plan` (csv_path)
- [x] Modifier `open_stack_plan_window.generate_plan` (csv_path)
- [x] Modifier `_create_simple_stack_plan` (csv_path)
- [x] Après write : `self.set_stack_plan_rows(csv_path)` (passer le path) + mettre à jour caches.
- [x] Priorité Project, fallback log, fallback cwd.

### 6) analyse_gui_qt.py : boutons export/script
- [x] Remplacer le connect direct :
  - [x] `stack_export_csv_btn.clicked.connect(self._export_stack_plan_csv)` -> `...connect(self._on_export_stack_plan_clicked)`
  - [x] `stack_prepare_script_btn.clicked.connect(self._prepare_stacking_script)` -> `...connect(self._on_prepare_stacking_script_clicked)`
- [x] Implémenter les deux handlers avec QFileDialog.

---

## Critères d’acceptation
1) [ ] Sélectionner un dossier Project contenant `stack_plan.csv` -> ouvrir l’onglet Stack plan -> le tableau se remplit sans action manuelle.
2) [ ] Changer de Project alors qu’on est sur Stack plan -> le tableau reflète le nouveau `stack_plan.csv`.
3) [ ] `Create stack plan` écrit désormais `Project/stack_plan.csv` (si Project valide) et l’onglet Stack plan affiche le fichier.
4) [ ] `Prepare stacking script` crée un script sur disque dans le Project par défaut, basé sur le plan chargé.
5) [ ] Aucune régression observable sur Preview autoload, Results, Organizer.

## Notes
- Ne pas changer `StackPlanModel` : il sait déjà lire un CSV via path string.
- Ne pas modifier le format CSV : rester compatible avec `stack_plan.write_stacking_plan_csv(csv_path, rows)` (ordre des args).
