
# Mission – ZeAnalyser GUI cross-platform + Qt parity

Tu es Codex.  
Tu travailles sur le projet **ZeAnalyser** (Tk = `analyse_gui.py`, Qt = `analyse_gui_qt.py`).

Objectif global :

1. **Corriger les problèmes de fenêtre "zoomed" / maximisée** pour que l’UI Tk fonctionne correctement sur **Windows, Linux/X11 et macOS**, sans lever d’erreur Tcl.
2. **Terminer le portage vers PySide6** : `analyse_gui_qt.py` doit offrir les mêmes fonctionnalités que `analyse_gui.py` pour :
   - le lancement d’analyse,
   - l’écriture du log,
   - le rechargement du log pour visualisation,
   - la gestion des marqueurs et du stack plan,
   - l’envoi de la référence au stacker.
3. Assurer que le **comportement fonctionnel** Tk ↔ Qt est cohérent (mêmes options, même logique, même fichiers produits) sans modifier la logique cœur (`analyse_logic.py`, modules SNR/FWHM/ECC/etc.).

Tu dois travailler **dans les fichiers suivants uniquement**, sauf si c’est explicitement demandé :

- `beforehand/analyse_gui.py` (GUI Tk, classe `AstroImageAnalyzerGUI`) :contentReference[oaicite:1]{index=1}  
- `beforehand/analyse_gui_qt.py` (GUI PySide6, classe `ZeAnalyserMainWindow`) :contentReference[oaicite:2]{index=2}  
- éventuellement `zone.py` **uniquement** pour ajouter des clés de traduction manquantes déjà utilisées dans le code.

Ne touche **pas** à :
- `analyse_logic.py`, `snr_module.py`, `ecc_module.py`, `starcount_module.py`, `trail_module.py`, `stack_plan.py`, etc. (logique d’analyse et stacking).  
- la structure du log (balises `--- BEGIN VISUALIZATION DATA ---` / `--- END VISUALIZATION DATA ---`), déjà utilisée pour la visualisation.

---

## 1. Compatibilité Tk : état de fenêtre "zoomed"

### Contexte

Sous Windows, il est courant de faire :

```python
root.state('zoomed')
````

Mais sous Linux/X11 ou certains WM, Tk ne connaît que les états :

* `"normal"`
* `"iconic"`
* `"withdrawn"`

Dans ce cas, passer `"zoomed"` provoque :

> `bad argument "zoomed": must be normal, iconic, or withdrawn`

### Tâches

1. **Créer un helper générique** dans `analyse_gui.py` (niveau module) :

   ```python
   def safe_set_maximized(root):
       """
       Met la fenêtre en mode maximisé de façon cross-platform.
       - Sous Windows: essaye state('zoomed') puis fallback.
       - Sous X11 / autres: utilise wm_attributes ou geometry, sans jamais lever d'exception.
       """
   ```

   Comportement attendu :

   * Utiliser `platform.system()` ou `sys.platform` pour détecter l’OS **ou**
   * Envelopper `root.state('zoomed')` dans un `try/except tk.TclError`.
   * Si `state('zoomed')` échoue, ne pas relancer l’exception. À la place :

     * tenter `root.wm_attributes('-zoomed', True)` si disponible, ou
     * sinon se contenter de `root.state('normal')` et éventuellement d’un léger agrandissement via `root.geometry(...)`.
   * Le helper **ne doit jamais** propager de `TclError`.

2. **Remplacer tous les appels directs** à `root.state('zoomed')`, `self.root.state('zoomed')`, etc. dans `AstroImageAnalyzerGUI` par un appel au helper `safe_set_maximized(self.root)`.

3. Vérifier qu’il n’y a **aucune autre** utilisation d’un état de fenêtre non standard dans `analyse_gui.py` (par exemple `wm_state('zoomed')`). Si oui, les passer par le même helper.

4. Le comportement visible doit rester :

   * Sous Windows : la fenêtre s’ouvre maximisée comme aujourd’hui.
   * Sous Linux/macOS : la fenêtre s’ouvre au mieux agrandie, **sans** message d’erreur.

---

## 2. Parité Tk ↔ Qt pour le lancement d’analyse et le log

### Objectif

Assurer que le bouton “Analyser les images” (et la variante “Analyser et Empiler”) dans le Qt GUI :

* prépare les **mêmes options** que Tk (SNR, trails, Bortle, tri, actions sur fichiers, etc.),
* appelle la **même fonction d’analyse** dans `analyse_logic`,
* produit un log qui contient le résumé + le bloc JSON de visualisation,
* permet ensuite de recharger les résultats pour la tab “Results” / “Stack Plan” comme Tk.

Tu peux t’appuyer sur la logique existante dans :

* `AstroImageAnalyzerGUI._launch_analysis(...)`, `run_analysis_thread(...)`, `write_log_summary(...)`, etc.
* `_load_visualization_data_from_log` dans `analyse_gui.py` (déjà prête à relire les données JSON). 

### Tâches

1. **Revoir la construction des options** dans `ZeAnalyserMainWindow._start_analysis()` et `_start_analysis_and_stack()` :

   * S’assurer que tous les champs utilisés par `analyse_logic.perform_analysis(...)` sont fournis :

     * `analyze_snr`, `detect_trails`, `include_subfolders`,
     * `bortle_path`, `use_bortle`,
     * `snr_selection_mode`, `snr_selection_value`,
     * `move_rejected`, `delete_rejected`,
     * `snr_reject_dir`, `trail_reject_dir`,
     * `apply_snr_action_immediately`, `apply_trail_action_immediately`, etc.
   * Calquer la même validation utilisateur que Tk :

     * erreur si dossier d’entrée invalide,
     * erreur si fichier log vide,
     * confirmation quand `delete_rejected=True`,
     * vérif des paramètres SNR et trails.

2. **S’assurer que l’appel à la logique d’analyse** Qt est bien aligné sur Tk.

   * Si une fonction `perform_analysis(...)` (ou équivalent) de `analyse_logic` est déjà utilisée dans Tk, utilise la **même signature**.
   * Conserver le pattern “thread de travail + callbacks” :

     * `status_callback` → mise à jour label de statut dans Qt,
     * `progress_callback` → barre de progression Qt,
     * `log_callback` → append dans la zone de log Qt.
   * Le thread ne doit jamais toucher directement à l’UI Qt (uniquement via signaux/slots si nécessaire).

3. **Écriture du résumé + bloc JSON** :

   * Vérifier que le thread d’analyse Qt appelle bien `analyse_logic.write_log_summary(...)` **avec `results_list` final** pour que le bloc JSON `--- BEGIN/END VISUALIZATION DATA ---` soit écrit, comme dans Tk. 
   * Ne pas changer le format : des tests et le code existant s’attendent précisément à ce layout.

4. **Rechargement des résultats dans Qt** :

   * Implémenter dans `ZeAnalyserMainWindow` un équivalent fonctionnel à `AstroImageAnalyzerGUI._load_visualization_data_from_log(...)` :

     * lecture du fichier log,
     * recherche du dernier bloc délimité par `--- BEGIN VISUALIZATION DATA ---` / `--- END VISUALIZATION DATA ---`,
     * `json.loads(...)` dans `self.analysis_results`,
     * calcul de `self.recommended_images` avec la même logique (utiliser `_compute_recommended_subset()` déjà présent en Qt).
   * Exposer une méthode genre `_load_visualisation_from_log_path(path)` appelée :

     * lorsque l’utilisateur clique sur “Visualiser les résultats”,
     * ou lorsque le champ “Log file” change et pointe vers un fichier existant.

5. **Remplir la table “Results”** :

   * À partir de `self.analysis_results` (liste de dicts comme en Tk), alimenter le `QTableView` de l’onglet “Results”.
   * La table doit contenir au minimum les colonnes :

     * chemin relatif,
     * SNR, starcount, FWHM, ECC,
     * statut, action, raison de rejet, présence de traînées, etc., comme dans Tk.
   * Utiliser un `QAbstractTableModel` léger, déjà présent si possible ; sinon en créer un dédié, en exposant :

     * `self._keys` = noms de colonnes,
     * `data(..., Qt.DisplayRole)` pour l’affichage,
     * `data(..., Qt.UserRole)` pour les valeurs brutes (utilisées par `ResultsFilterProxy`).

6. **Filtres et tris** :

   * Raccorder correctement `ResultsFilterProxy` :

     * `self.results_view.setModel(self.results_proxy)`,
     * `self.results_proxy.setSourceModel(self.results_model)`.
   * Brancher les champs de filtres (`snr_min_edit`, etc.) sur les attributs :

     * `proxy.snr_min`, `proxy.snr_max`, `proxy.fwhm_max`, `proxy.ecc_max`, `proxy.has_trails`,
     * en les mettant à `None` quand le champ est vide.
   * Si la case “Sort by descending SNR” est cochée, appliquer un tri sur la colonne SNR.

---

## 3. Gestion des marqueurs, “Manage Markers” et Stack Plan (Qt)

Dans le Tk GUI, la fin d’analyse peut générer des **fichiers marqueurs** (par ex. `.astro_analyzer_run_complete`, fichiers CSV de pollution, etc.), et le bouton “Gérer Marqueurs” devient cliquable si un marqueur existe dans le dossier d’entrée.

### Tâches

1. **Reprendre la même logique de détection** des marqueurs que dans `AstroImageAnalyzerGUI` (chercher les fichiers/flags utilisés) et l’implémenter dans `ZeAnalyserMainWindow` :

   * Lorsqu’un dossier d’entrée est sélectionné, scanner rapidement pour détecter ces fichiers.
   * Si au moins un marqueur est trouvé, activer `self.manage_markers_btn`, sinon le désactiver.

2. **Porter la logique de “Manage Markers”** :

   * Créer une méthode `_manage_markers()` dans Qt qui :

     * soit ouvre un dialogue Qt dédié (si la logique existe déjà côté Tk) ;
     * soit, au minimum, propose un message d’information et/ou ouvre le dossier contenant les marqueurs.
   * Le comportement n’a pas besoin d’être pixel-perfect mais doit offrir le **même niveau de fonctionnalité** que Tk (ex. création, suppression ou édition des marqueurs).

3. **Création de Stack Plan** :

   * Reprendre le comportement du bouton “Créer plan de stack” de Tk :

     * s’assurer que le bouton Qt “Create stacking plan” appelle une fonction qui lit `self.analysis_results` et génère un fichier CSV via `stack_plan.generate_stacking_plan(...)` / `write_stacking_plan_csv(...)`.
   * Stocker le chemin du dernier stack plan généré pour l’afficher ou le réouvrir plus tard.
   * Mettre à jour la tab “Stack Plan” avec un aperçu des batchs générés (un simple tableau issu du CSV est suffisant).

---

## 4. Communication avec le stacker, bouton “Analyser et Empiler”

`analyse_gui.py` gère déjà la logique :

* `start_analysis()` → lance uniquement l’analyse.
* `start_analysis_and_stack()` → lance l’analyse **puis** écrit un fichier de commande pour le stacker **si** le token `token.zsss` est présent dans le dossier parent du projet. 

### Tâches

1. **Aligner Qt sur Tk pour la détection du token** :

   * `ZeAnalyserMainWindow` détecte déjà une `parent_token_file_path` et un booléen `parent_token_available`. Vérifier/terminer cette logique pour qu’elle fasse la même chose que Tk (même chemin, mêmes prints de debug).
   * Si le token est présent, autoriser le bouton “Analyze and Stack” (`analyse_and_stack_btn`), sinon le désactiver avec un message dans le log type “token.zsss introuvable…”.

2. **Implémenter le flux “Analyze and Stack”** dans Qt :

   * `self._start_analysis_and_stack()` doit :

     * lancer l’analyse avec un flag interne `self.stack_after_analysis = True`;
     * lorsque l’analyse se termine avec succès, écrire le fichier de commande attendu par le stacker (même format que Tk) à l’emplacement configuré (`self.command_file_path` ou équivalent);
     * si possible, notifier l’utilisateur dans le log Qt (ligne “Fichier de commande écrit : …”).

3. **Assurer que ce flux reste un sur-ensemble du flux “Analyze only”** :

   * éviter la duplication de code inutile : factoriser dans une méthode interne commune (ex. `_run_analysis(stack_after: bool)`).

---

## 5. I18n, tooltips et cohérence UI

1. **Traductions manquantes** : si les clés utilisées par Qt (ex. `apply_immediately`, `stack_export_csv`, `stack_prepare_script`, `help_menu_label`, `about_action_label`, etc.) ne figurent pas dans `zone.translations`, les ajouter **dans `zone.py` uniquement** avec des équivalents FR/EN raisonnables.

2. **Tooltips** :

   * Tk a déjà une logique de `ToolTip` pour expliquer les options aux utilisateurs. Sans nécessairement tout recopier, ajouter au moins des tooltips sur les contrôles importants dans Qt :

     * options SNR,
     * détection de traînées,
     * actions sur fichiers,
     * options de recommandation (SNR/FWHM/ECC/starcount).
   * Utiliser `setToolTip()` côté Qt.

3. **État des boutons** :

   * Vérifier que tous les boutons sensibles (`Visualise Results`, `Apply Recommendations`, `Manage Markers`, `Create stacking plan`, etc.) sont correctement activés/désactivés en fonction de :

     * présence d’un log exploitable,
     * présence de `analysis_results`,
     * présence de `recommended_images`.

---

## 6. Validation & non-régressions

1. **Lancer l’application Tk** sur Windows et Linux (ou WSL+X11) après tes modifications pour vérifier :

   * aucun message “bad argument 'zoomed'”,
   * la fenêtre s’ouvre correctement,
   * l’analyse et la visualisation fonctionnent comme avant.

2. **Lancer l’application Qt** avec un dossier de test :

   * remplir les champs Input/Log,
   * lancer une analyse,
   * vérifier :

     * la progression et les statuts,
     * la présence du résumé + bloc JSON dans le log,
     * que l’onglet Results montre bien les données,
     * que les filtres SNR/FWHM/ECC/Trails fonctionnent,
     * que “Create stacking plan” produit un CSV cohérent,
     * que “Manage Markers” se déverrouille dès qu’un marqueur est présent.

3. Ne commettre **aucune modification** qui changerait le format du log ou la structure des dictionnaires de résultats.

