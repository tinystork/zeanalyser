# 🎯 Mission : ZeAnalyser Qt – Remise sur rails & parité avec l’UI Tk

Objectif immédiat :  
Amener l’UI **Qt** au niveau fonctionnel de l’UI **Tk** actuelle pour l’onglet **Projet** et l’onglet **Résultats**, **sans toucher à la logique métier** ni aux formats CSV.

La base Qt est déjà en place (fenêtre, worker, tableau de résultats + filtres).  
La mission est maintenant de **porter les contrôles Tk restants** et de **rebrancher les mêmes options**.

---

## 📦 Contexte

- UI actuelle de référence : `analyse_gui.py` (Tkinter), qui contient :
  - Toute la **configuration d’analyse** (SNR, traînées, Bortle, rejet, actions, etc.).
  - La logique de construction du dict `options` passé à `perform_analysis()`.
  - Les handlers des boutons : analyser, analyser & empiler, créer plan de stack, gérer marqueurs, etc.   

- UI Qt expérimentale : `analyse_gui_qt.py` :
  - Onglet **Project** minimal (sélecteur input, log, SNR on/off, trails on/off, Analyse/Annuler, barre de progression, log texte). :contentReference[oaicite:8]{index=8}  
  - Worker Qt (`AnalysisWorker`, `AnalysisRunnable`) déjà fonctionnel et câblé à `perform_analysis()`. :contentReference[oaicite:9]{index=9}  
  - Onglet **Results** avec `QTableView` + `AnalysisResultsModel` + `ResultsFilterProxy` et filtres SNR/FWHM/ECC/Trails.   

- Modèle / schéma de résultats :
  - `analysis_model.py` + `analysis_schema.py` définissent l’ordre des colonnes et exposent les lignes (dicts) au QTableView.   

---

## ❗ Contraintes non négociables

- **Ne pas modifier** la logique métier dans :
  - `analyse_logic.py`,
  - `snr_module.py`, `ecc_module.py`, `trail_module.py`, `sat_trail.py`,
  - `stack_plan.py`,
  - `bortle_utils.py`, `bortle_thresholds.json`.   
- **Ne pas changer** les formats CSV (colonnes, ordre, séparateurs, encodage) ni les logs.
- **Ne pas renommer / supprimer** les tokens utilisés par `zone.py`, la détection ZeSeestarStacker / ZeMosaic, ou la CLI.
- Garder l’UI Tk **opérationnelle** en parallèle (aucun comportement cassé).
- Ne pas réindenter massivement les vieux fichiers (diff propres).

---

## 🧱 Architecture Qt à respecter

- `analyse_gui_qt.py` :
  - `ZeAnalyserMainWindow(QMainWindow)` avec :
    - Onglet **Project** (config d’analyse, boutons).
    - Onglet **Results** (table de résultats + filtres).
    - (Plus tard) onglets **Stack Plan**, **Preview**, etc.
- Worker d’analyse :
  - `AnalysisWorker` / `AnalysisRunnable` déjà présents → **ne pas refondre**, seulement **réutiliser**. :contentReference[oaicite:13]{index=13}  
- Modèles Qt :
  - `AnalysisResultsModel` + `ResultsFilterProxy` pour les résultats.   
  - Plus tard : `StackPlanModel` pour le CSV de stack plan.

---

## 🧩 Plan de travail révisé (petites étapes)

### Phase 3A – Parité “Configuration générale” du tab Projet

Objectif : reproduire la section **Configuration Générale** de Tk dans l’onglet **Project** Qt.

À faire dans `ZeAnalyserMainWindow._build_ui()` (ou méthodes dédiées) :

 - [X] Ajouter un `QGroupBox` ou équivalent “Configuration générale” contenant :
  - [X] `Dossier d’entrée` (déjà présent, réordonner si besoin).
  - [X] `Fichier log` (déjà présent).
  - [X] Checkbox **“Inclure les sous-dossiers”** (`include_subfolders`).
  - [X] Champ **Base Bortle (GeoTIFF/KMZ)** (`bortle_path`) + bouton `Parcourir…`.
  - [X] Checkbox **“Utiliser le classement Bortle”** (`use_bortle`).
  - [X] Bouton `Organiser fichiers` (reprend exactement la logique Tk existante).
- [X] Ajouter un sélecteur de langue (combo) en bas de la section, avec la valeur initiale identique à Tk (via `zone.py` / config).
- [X] Créer une méthode `_build_options_from_ui()` qui construit le dict `options` pour `perform_analysis()` **en miroir** de ce que fait Tk (`start_analysis()` / `_launch_analysis()` dans `analyse_gui.py`).

**Livrable Phase 3A** :  
Le tab **Project** en Qt expose la même config générale que Tk, et `options` (include_subfolders, bortle_path, use_bortle…) passent correctement à `perform_analysis()`.

---

### Phase 3B – Parité “Analyse SNR & Sélection”

Objectif : porter la section **Analyse SNR & Sélection**.

À faire :

- [X] Ajouter un `QGroupBox` “Analyse SNR & Sélection” avec :  
  *(implémenté dans `analyse_gui_qt.py`; test ajouté `tests/test_analyse_gui_snr.py`)*
  - [X] Checkbox `Activer l’analyse SNR` (lié à `options['analyze_snr']`).  
    *(implémenté et testé : `analyse_gui_qt.py` / `tests/test_analyse_gui_snr.py`)*
  - [X] Radio-boutons pour le **mode de sélection** :  
    *(Top Pourcentage / Seuil SNR / Tout garder — implemented in `analyse_gui_qt.py` and covered by tests)*
    - `Top Pourcentage (%)` (`mode='percent'` + `value`),
    - `Seuil SNR (>)` (`mode='threshold'` + `value`),
    - `Tout garder` (`mode='all'` ou équivalent utilisé en Tk).
  - [X] Champ numérique pour le pourcentage / seuil SNR.  
    *(QDoubleSpinBox `snr_value_spin` added and used by `_build_options_from_ui()` — tests cover value extraction)*
  - [X] Champ `Dossier Rejet (Faible SNR)` (`snr_reject_dir`).  
    *(text field + browse button added; value included in `_build_options_from_ui()`)*
  - [X] Bouton `Appliquer Rejet SNR` qui appelle la même logique que Tk (factorisé vers `analyse_logic.apply_pending_snr_actions`).  
    *(implémenté — see `analyse_gui_qt.py` and `tests/test_analyse_gui_snr.py`)*
- [X] Brancher ces contrôles dans `_build_options_from_ui()` (options `apply_snr_action_immediately`, `move_rejected`, `delete_rejected`, etc., exactement comme en Tk).  
  *(snr_mode/sn r_value/snr_reject_dir/apply flags included)*

**Livrable Phase 3B** :  
En Qt, lancer une analyse avec SNR activé/rejet configuré produit le **même comportement** (fichiers déplacés / marqués) que depuis Tk.

---

### Phase 3C – Parité “Détection Traînées + Actions sur images rejetées”

Objectif : porter la section **Détection Traînées** et **Action sur images rejetées**.

 - [X] Ajouter un `QGroupBox` “Détection Traînées” avec :  
   *(implémenté dans `analyse_gui_qt.py` — widgets et tests ajoutés `tests/test_analyse_gui_trails.py`)*
  - [X] Checkbox `Activer détection traînées` ↔ `options['detect_trails']`.
  - [X] Champs numériques : `sigma`, `low_thr`, `high_thr`, `line_len`, `small_edge`, `line_gap`.
  - [X] Champ `Dossier Rejet (Traînées)` (`trail_reject_dir`).
  - [X] Bouton `Appliquer Rejet Traînées` (implémenté et testé `tests/test_analyse_gui_trails.py`).
- [X] Ajouter un `QGroupBox` “Action sur images rejetées” avec radios :  
  *(implémenté — radio buttons move/delete/none added and wired into `_build_options_from_ui()`)*
  - [X] `Déplacer vers dossier Rejet` → `options['move_rejected']=True`, `delete_rejected=False`.
  - [X] `Supprimer définitivement` → `delete_rejected=True`.
  - [X] `Ne rien faire` → les deux False.
- [X] Adapter `_build_options_from_ui()` pour refléter exactement la logique Tk (y compris validations d’entrées et messages d’erreur).  
  *(basic validation implemented in `_start_analysis()` — missing target dirs prevent starting and log an error; tests added)*

**Livrable Phase 3C** :  
Les analyses Qt avec détection de traînées + stratégie de rejet configurée se comportent comme Tk (mêmes options, mêmes effets).

---

### Phase 3D – Barre d’actions du bas + tris d’affichage

Objectif : amener les boutons et options d’affichage au même niveau.

  - [X] Ajouter un `QGroupBox` ou layout pour :
  - [X] Checkbox `Trier les résultats par SNR décroissant` :
    - soit en demandant au `QTableView` de trier sur la colonne SNR en desc,
    - soit en ajustant le `QSortFilterProxyModel`.
  - [X] Barre de boutons avec :
    - [X] `Analyser les images` (déjà présent : alias de `Analyser`).
    - [X] `Analyser et Empiler` (implémenté: `analyse_and_stack_btn` → `_start_analysis_and_stack()`).
    - [X] `Ouvrir le fichier log` (implémentation best-effort: `_open_log_file`).
    - [X] `Créer plan de stack` (stubbed: `_create_stack_plan`, tries to call `stack_plan` module when available).
    - [X] `Gérer marqueurs`, `Visualiser les résultats`, `Appliquer Recommandations`, `Envoyer/Sauvegarder Référence` :
      - **OK** que certains restent désactivés/“stub” dans un premier temps, mais ils doivent être présents visuellement.
    - [X] `Quitter` (fermeture propre de la fenêtre Qt).
- [X] Ajouter `Temps écoulé` / `Temps restant` dans la barre d’état (statusBar) ou comme labels en bas, alimentés par les infos du worker ou un chrono interne.
  *(placeholders added as labels in the bottom action bar)*

**Livrable Phase 3D** :  
L’onglet Project Qt ressemble fonctionnellement à la fenêtre Tk : mêmes boutons, même ergonomie générale.

---

### Phase 4 – Stack Plan viewer (comme avant mais Qt)

(Ne démarrer qu’une fois 3A–3D OK.)

- [X] Créer un `StackPlanModel(QAbstractTableModel)` lisant le CSV produit par `stack_plan.py` **sans changer le format**.
- [X] Onglet “Stack Plan” avec un `QTableView` triable/filtrable.
  - [X] Indicateurs visuels (par dossier / nuit / Bortle) via couleurs ou tri.
 - [X] Indicateurs visuels (par dossier / nuit / Bortle) via couleurs ou tri.
 - [X] Boutons légers pour des actions non destructives (préparer scripts, etc.).

---

### Phase 5 – Preview image + histogramme (simple)

- [X] Onglet/panneau “Preview” :
  - sélection d’une ligne dans la table de résultats → chargement de l’image correspondante (FITS/PNG).
  - affichage via un canvas Qt (zoom/pan basiques).
- [X] Histogramme (Matplotlib backend Qt) avec sliders min/max.

---

### Phase 6 – Traductions / zones

- [X] Analyser `zone.py` et le système actuel de tokens.
- [X] Ajouter un petit wrapper Qt de traduction pour réutiliser les mêmes textes.
- [X] Remplacer les labels hardcodés du GUI Qt par des appels à ce wrapper.

---

### Phase 7 – Confort UX & settings

 - [X] Tooltips sur les contrôles importants.

---

### Phase 8 – Coexistence Tk / Qt

- [ ] Entry point propre pour Qt (ex : `python -m zeanalyser_qt`).
- [ ] Documentation courte (README ou doc) expliquant comment lancer ZeAnalyser Qt.
- [ ] Vérifier que Tk continue à fonctionner.

---

## ✅ Règles de travail pour Codex

- Toujours comparer la logique Qt avec celle de `analyse_gui.py` avant d’inventer quelque chose.
- Procéder **par sous-phase** (3A, 3B, 3C, etc.) → un ensemble de commits courts, ciblés.
- Ne pas modifier les signatures de `perform_analysis()` ni les clés `options` sans nécessité absolue.
- Ne pas casser les tests existants (UI worker, modèle de résultats, filtres).
- Ajouter des commentaires dans `analyse_gui_qt.py` là où la logique est un mirror de Tk (pour faciliter la review).
