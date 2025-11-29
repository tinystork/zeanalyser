# 📋 ZeAnalyser Qt – Suivi & Check-list

Ce fichier est le journal de bord pour la migration Tk → PySide6.

Coche les cases `[x]` au fur et à mesure et ajoute des notes si besoin.

---

## Phase 1 – Base PySide6 (terminée)

- [x] `analyse_gui_qt.py` créé, avec `ZeAnalyserMainWindow(QMainWindow)`.
- [x] `QApplication` + boucle d’événements fonctionnelle.
- [x] Onglet/panneau “Project” minimal (chemins + bouton “Analyser”).
- [x] Simulation de progression (sans vraie analyse) opérationnelle.
- [x] Test manuel : l’app Qt démarre et se ferme proprement.

Notes :
- OK, base Qt stable.

---

## Phase 2 – Worker & vrais calculs (terminée)

- [x] `AnalysisWorker(QObject)` créé avec signaux Qt.
- [x] Intégration de `perform_analysis()` (logique existante).
- [x] Mise en place de `QThread`/`QThreadPool`.
- [x] Connexion des signaux aux widgets (status, log, barre de progression).
- [x] Test : une vraie analyse complète se termine sans freeze UI.
- [x] Signal `resultsReady` émis avec les résultats d'analyse; connexion à `set_results()`.
- [x] Callbacks `status`, `progress`, `log`, `is_cancelled` transmis à `perform_analysis()`.

Notes :
- Phase 2 validée ✅ (tests d’intégration worker/GUI OK).

---

## Phase 3 – Tableau de résultats (terminée)

- [x] Structure des résultats d’analyse identifiée (dicts).
- [x] `AnalysisResultsModel` implémenté (QAbstractTableModel).
- [x] `QTableView` + `ResultsFilterProxy` branchés.
- [x] Filtres numériques / booléens (SNR, FWHM, ecc, has_trails) opérationnels.
- [x] Test : tri + filtres OK sur un dataset réel.

Notes :
- L’onglet **Results** sert de référence pour la suite (logique de filtres).

---

## Phase 3A – Parité “Configuration générale” (à faire)

 - [X] GroupBox “Configuration générale” ajouté dans l’onglet Project.
- [X] Checkbox **Inclure les sous-dossiers** branchée sur `options['include_subfolders']`.
- [X] Champ **Base Bortle (GeoTIFF/KMZ)** + bouton `Parcourir`.
- [X] Checkbox **Utiliser le classement Bortle** (`options['use_bortle']`).
- [X] Bouton **Organiser fichiers** (reprend la logique Tk existante).
- [X] Sélecteur de langue (combo) relié à `zone.py` / config.
- [X] Méthode `_build_options_from_ui()` créée (ou complétée) pour construire le dict `options` en miroir de Tk.

Notes :

---

## Phase 3B – Parité “Analyse SNR & Sélection” (à faire)

- [X] GroupBox “Analyse SNR & Sélection” ajouté.  
  *(implémenté dans `analyse_gui_qt.py`; test ajouté `tests/test_analyse_gui_snr.py`)*
- [X] Checkbox `Activer l’analyse SNR` ↔ `options['analyze_snr']`.  
  *(implémenté et testé : `analyse_gui_qt.py` / `tests/test_analyse_gui_snr.py`)*
- [X] Radios de mode : Top Pourcentage / Seuil SNR / Tout garder.  
  *(implemented in `analyse_gui_qt.py` — test ensures mode/value captured in options)*
- [X] Champ numérique pour valeur de pourcentage / seuil.  
  *(implemented as `snr_value_spin` and included in `_build_options_from_ui()` tests)*
- [X] Champ `Dossier Rejet (Faible SNR)` (`snr_reject_dir`).  
  *(text field + browse implemented and value included in options)*
- [X] Bouton `Appliquer Rejet SNR` branché sur la même logique que Tk.  
  *(calls `analyse_logic.apply_pending_snr_actions` in background; tested by `tests/test_analyse_gui_snr.py`)*
- [X] `_build_options_from_ui()` met à jour `options` (mode de sélection, `apply_snr_action_immediately`, etc.).  
  *(function expanded to include `snr_mode`,`snr_value`,`snr_reject_dir`,`apply_snr_action_immediately` — see `tests/test_analyse_gui_snr.py`)*
- [X] Test : comparer comportement Qt/Tk sur un dataset (mêmes fichiers rejetés/déplacés).  
  *(lightweight parity test added: `tests/test_analyse_gui_snr.py::test_qt_and_tk_apply_parity` — validates both frontends flag the same files for SNR apply)*

Notes :

---

## Phase 3C – Parité “Détection Traînées + Actions rejet” (à faire)

 - [X] GroupBox “Détection Traînées” ajouté.
 - [X] Checkbox `Activer détection traînées` ↔ `options['detect_trails']`.
 - [X] Paramètres (sigma, low_thr, high_thr, line_len, small_edge, line_gap) exposés et passés à `perform_analysis()`.
 - [X] Champ `Dossier Rejet (Traînées)` (`trail_reject_dir`).
 - [X] GroupBox “Détection Traînées” ajouté.  
   *(implémenté dans `analyse_gui_qt.py` — widgets and `tests/test_analyse_gui_trails.py` added)*
 - [X] Checkbox `Activer détection traînées` ↔ `options['detect_trails']`.
 - [X] Paramètres (sigma, low_thr, high_thr, line_len, small_edge, line_gap) exposés et passés à `perform_analysis()`.
 - [X] Champ `Dossier Rejet (Traînées)` (`trail_reject_dir`).
- [X] GroupBox “Action sur images rejetées” avec radios move/delete/none.  
  *(implemented in `analyse_gui_qt.py`; see `tests/test_analyse_gui_reject_actions.py`)*
- [X] `_build_options_from_ui()` met à jour `move_rejected`, `delete_rejected`, etc.  
  *(radio selection flows into options; validations implemented in `_start_analysis` — see `tests/test_analyse_gui_validations.py`)*
 - [X] Test : comparer comportement Qt/Tk sur un dataset (rejets identiques).  
   *(parity tests added for trails: `tests/test_analyse_gui_trails.py`)*

Notes :

---

## Phase 3D – Barre d’actions + tris (à faire)

- [X] Checkbox `Trier les résultats par SNR décroissant` reliée au `QSortFilterProxyModel` ou au `QTableView`.
  *(implemented — checkbox calls `_on_sort_by_snr_changed` and sorts proxy by `snr` column)*
- [X] Bouton `Analyser les images` (alias de l’action actuelle).
- [X] Bouton `Analyser et Empiler` implémenté (logique de `start_analysis_and_stack()` portée).
  *(added `analyse_and_stack_btn`, calls `_start_analysis_and_stack` which sets stack-after flag and starts analysis)*
- [X] Bouton `Ouvrir le fichier log` opérationnel.  *(best-effort opening of log file via `_open_log_file`)*
- [X] Bouton `Créer plan de stack` → appelle `stack_plan.py` comme Tk.  *(stubbed call implemented; logs when module absent)*
 - [X] Boutons `Envoyer Référence` / `Sauvegarder Référence` / `Visualiser les résultats` / `Gérer Marqueurs` / `Appliquer Recommandations` :
  - [X] présents visuellement,
  - [X] soit connectés, soit explicitement désactivés avec TODO.
- [X] Bouton `Quitter` ferme la fenêtre Qt proprement.
- [X] Labels `Temps écoulé` / `Temps restant` ajoutés et mis à jour.  *(placeholders implemented in action bar)*

Notes :

---

## Phase 4 – Stack Plan viewer (à venir)

  - [X] `StackPlanModel` implémenté.  
   *(implemented in `analysis_model.py` — `StackPlanModel` available)*
 - [X] Onglet “Stack Plan” avec tableau triable + filtrable.  
   *(implemented `analyse_gui_qt.set_stack_plan_rows()` with QTableView + proxy)*
    - [X] Indicateurs visuels par groupe/nuit/Bortle.
 - [X] Test : contenu du tableau identique au CSV.  
   *(tests added: `tests/test_stack_plan_model.py`, `tests/test_stack_plan_tab.py` — verify CSV round-trip and UI integration)*

Notes :

---

 ## Phase 5 – Preview image (à venir)

- [X] Onglet/panneau “Preview” créé.
- [X] Sélection d’une image dans la table des résultats met à jour la preview.
- [X] Affichage FITS/PNG de base (zoom/pan).
- [X] Histogramme + stretch min/max simple.

Notes :

---

## Phase 6 – Traductions & zones (à venir)
 [X] Analyse de `zone.py` et du système de tokens réalisée.
- [X] Wrapper de traduction Qt créé.
- [X] Textes UI Qt remplacés par le wrapper.
- [ ] Test : libellés Tk vs Qt identiques pour un même run.

Notes :

---

## Phase 7 – Confort UX (à venir)

- [X] `QSettings` pour mémoriser dossiers, taille/position, paramètres.
- [X] Menu `Aide → À propos` ajouté.
- [X] Tooltips sur les contrôles critiques.
- [ ] Sauvegarde/restauration de l’état à la fermeture.

Notes :

---

## Phase 8 – Coexistence Tk / Qt (à venir)

- [ ] Entrypoint Qt dédié (ex. `python -m zeanalyser_qt`).
- [ ] UI Tk vérifiée comme toujours fonctionnelle.
- [ ] Doc/README mis à jour (Qt en option, statut BETA).

Notes :
