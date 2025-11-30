## `followup.md`

# Suivi – ZeAnalyser GUI cross-platform + Qt parity

Coche chaque étape quand elle est terminée.

## 1. Compatibilité Tk – état de fenêtre

- [X] Créer `safe_set_maximized(root)` dans `analyse_gui.py` qui :
  - [X] Essaye `root.state('zoomed')` sous Windows, dans un `try/except tk.TclError`.
  - [X] Si erreur (X11/macOS), utilise un fallback inoffensif (`state('normal')`, `wm_attributes`, ou simple geometry), **sans** remonter d’exception.
- [X] Remplacer tous les appels directs à `state('zoomed')` par `safe_set_maximized(self.root)`.
- [X] Vérifier qu’aucun autre état non standard n’est passé à `state` / `wm_state`.
- [ ] Tester sous Windows (doit rester maximisé) et sous Linux (plus d’erreur “bad argument 'zoomed'”).

## 2. Lancement d’analyse & log en Qt

- [ ] Harmoniser `_start_analysis()` et `_start_analysis_and_stack()` dans `ZeAnalyserMainWindow` pour construire le même dict `options` que Tk :
  - [ ] SNR / trails / subfolders / Bortle / actions / chemins de rejet.
  - [ ] Validation des entrées (dossier, log, pourcentage SNR, params trails, confirm delete).
- [ ] Vérifier que l’appel à la logique d’analyse Qt utilise la même fonction que Tk (`analyse_logic.perform_analysis(...)` ou équivalent).
- [ ] Confirmer que le thread Qt appelle `write_log_summary(...)` avec `results_list` final pour générer le bloc JSON.
- [ ] Implémenter une méthode Qt type `_load_visualisation_from_log_path(path)` qui :
  - [ ] lit file,
  - [ ] trouve le dernier bloc JSON entre `--- BEGIN/END VISUALIZATION DATA ---`,
  - [ ] remplit `self.analysis_results`,
  - [ ] appelle `_compute_recommended_subset()`.

## 3. Remplissage de l’onglet “Results”

- [ ] Créer un `QAbstractTableModel` (ou utiliser celui existant) pour `self.analysis_results`, avec :
  - [ ] `self._keys` = colonnes,
  - [ ] `data(..., DisplayRole)` pour l’affichage,
  - [ ] `data(..., UserRole)` pour les valeurs brutes.
- [ ] Brancher `ResultsFilterProxy` :
  - [ ] `self.results_proxy.setSourceModel(self.results_model)`,
  - [ ] `self.results_view.setModel(self.results_proxy)`.
- [ ] Relier les champs de filtre (SNR/FWHM/ECC/has_trails) à `ResultsFilterProxy`.
- [ ] Implémenter le tri SNR décroissant quand la checkbox correspondante est cochée.

## 4. Marqueurs, “Manage Markers” & Stack Plan

- [ ] Reprendre dans Qt la logique Tk de détection de fichiers marqueurs dans le dossier d’entrée.
- [ ] Activer/désactiver `manage_markers_btn` en conséquence.
- [ ] Implémenter `_manage_markers()` côté Qt avec un comportement cohérent (gestion ou au minimum affichage des marqueurs / ouverture du dossier).
- [ ] Relier le bouton “Create stacking plan” au même pipeline que Tk :
  - [ ] Utiliser `stack_plan.generate_stacking_plan(...)` / `write_stacking_plan_csv(...)` pour produire le CSV.
  - [ ] Stocker le chemin du dernier plan,
  - [ ] Remplir la tab “Stack Plan” avec un aperçu (lecture du CSV dans un modèle Qt).

## 5. “Analyze and Stack” & token

- [ ] Vérifier la détection du `token.zsss` dans `ZeAnalyserMainWindow.__init__` (même chemin et logique que Tk).
- [ ] Si le token est absent, désactiver `analyse_and_stack_btn` et logguer un warning.
- [ ] Implémenter `_start_analysis_and_stack()` :
  - [ ] lancer l’analyse avec un flag interne `self.stack_after_analysis`,
  - [ ] en fin d’analyse, si succès :
    - [ ] écrire le fichier de commande vers le stacker au format attendu par Tk,
    - [ ] logguer le chemin du fichier de commande.
- [ ] Factoriser au maximum la logique commune entre “Analyze only” et “Analyze and Stack”.

## 6. I18n, tooltips, état des boutons

- [ ] Ajouter dans `zone.py` les clés manquantes utilisées par Qt (FR/EN au minimum).
- [ ] Positionner des tooltips Qt sur les contrôles clés (SNR, trails, actions, recommandations).
- [ ] Vérifier que les boutons :
  - [ ] “Visualise Results”
  - [ ] “Apply Recommendations”
  - [ ] “Manage Markers”
  - [ ] “Create stacking plan”
  sont correctement activés/désactivés selon l’état (`analysis_results`, log présent, etc.).

## 7. Tests finaux

- [ ] Lancer le Tk GUI sur Windows et Linux, valider :
  - [ ] pas d’erreur “zoomed”,
  - [ ] analyse + visualisation OK.
- [ ] Lancer le Qt GUI avec un jeu de données de test, valider :
  - [ ] analyse complète, progression, statut,
  - [ ] log avec résumé + bloc JSON,
  - [ ] onglet Results peuplé + filtres fonctionnels,
  - [ ] stack plan généré et visible,
  - [ ] gestion des marqueurs opérationnelle,
  - [ ] flux “Analyze and Stack” écrit bien le fichier de commande lorsqu’un `token.zsss` est présent.

Quand toutes les cases sont cochées, le portage Qt et la compatibilité multi-plateforme sont considérés comme terminés.
