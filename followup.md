# followup.md — Suivi mission ZeAnalyser Qt (analyse_gui_qt.py)

## 🔎 Rappel rapide de la mission

Objectif : finaliser l’intégration Qt de ZeAnalyser pour que :

- l’analyse réelle tourne via `analyse_logic.perform_analysis`,
- le **log** soit correctement alimenté (fichier + zone texte),
- les **résultats complets** remontent dans l’onglet *Results*,
- les **boutons bas de fenêtre** (stack plan, markers, visualisation, recos…) fonctionnent comme prévu,
- le tout sans casser le comportement existant (Tk, logique d’analyse).

---

## ✅ État courant (à vérifier avant de modifier)

- [x] Le projet compile et `python analyse_gui_qt.py` lance bien la fenêtre principale.
- [x] La sélection de dossier d’entrée met à jour :
  - [x] `input_path_edit`
  - [x] `log_path_edit`
  - [x] les dossiers de rejet SNR / traînées
- [x] Le bouton **Analyser** déclenche bien la création d’un `AnalysisWorker` et la connexion de ses signaux.
- [x] Le fichier `analyse_resultats.log` est créé lors d’une analyse (même si elle est encore en mode “simulation”).

---

## 🧩 Étape 1 — Corriger et consolider `AnalysisWorker`

### 1.1 Réécrire proprement `_tick` (dans `AnalysisWorker`)

- [x] Supprimer toute référence directe à des widgets (progress bar, etc.) dans `_tick`.
- [x] Utiliser un compteur interne (par ex. `self._progress`) pour simuler la progression si besoin.
- [x] Émettre `self.progressChanged.emit(value)` à chaque tick.
- [x] Arrêter le timer et émettre `self.finished(False)` lorsque la progression atteint 100%.
- [x] Appeler `_clean_thread()` dans tous les cas (fin normale ou annulée).

### 1.2 S’assurer que `_run_analysis_callable` respecte le protocole de callbacks

- [x] Récupérer correctement `log_callback` depuis `kwargs.pop('log_callback', ...)`.
- [x] Construire `callbacks = {'status', 'progress', 'log', 'is_cancelled'}`.
- [x] Passer `callbacks` en **dernier argument positionnel** au `analysis_callable`.
- [x] Émettre :
  - [x] `progressChanged(100.0)` en fin de run.
  - [x] `resultsReady(result)` si `result` est non nul.
  - [x] `finished(self._cancelled)` dans un bloc `finally`.
- [x] En cas d’exception, émettre aussi `error(str(e))` avant `finished(...)`.

---

## 🧠 Étape 2 — Intégration avec `analyse_logic.perform_analysis`

### 2.1 Aligner la signature de `perform_analysis`

- [x] Vérifier la signature actuelle de `analyse_logic.perform_analysis`.
- [x] L’adapter si nécessaire pour qu’elle accepte :  
      `perform_analysis(input_path, output_path, options, callbacks)`.
- [x] Garantir que la fonction utilise **exclusivement** `callbacks['log']`, `callbacks['progress']`, etc. pour communiquer.

### 2.2 Remontée des résultats dans le modèle Qt

- [x] Faire en sorte que `perform_analysis(...)` retourne une **liste de dicts** de résultats (idéalement la même structure que Tk).
- [x] Adapter (si besoin) `AnalysisResultsModel` pour mapper ces clés :
  - [x] SNR
  - [x] FWHM
  - [x] e (excentricité)
  - [x] fond / bruit / PixSig
  - [x] starcount (si disponible)
  - [x] traînées (bool + nombre)
  - [x] statut / action
- [x] Dans `_on_results_ready`, appeler `self.set_results(results)` AVANT toute logique de boutons.
- [x] Vérifier que le tri par SNR fonctionne (données numériques bien exposées via `Qt.UserRole`).

> Si `perform_analysis` ne peut pas raisonnablement renvoyer les résultats :
> - [ ] Ajouter une fonction utilitaire dans `analyse_logic` (ex. `load_analysis_results(log_file)`) pour parser le log ou CSV.
> - [ ] L’appeler dans `_on_worker_finished` si `results` est `None`.

---

## 📝 Étape 3 — Log (fichier + widget)

### 3.1 Pipeline `callbacks['log']` → `log_callback` → widget

- [x] Vérifier que `log_callback` dans `_start_analysis` :
  - [x] traduit correctement `text_key` via `_translate`,
  - [x] ajoute le timestamp `[HH:MM:SS]`,
  - [x] écrit dans le fichier `analyse_resultats.log`,
  - [x] émet `w.logLine.emit(full_text)`.
- [x] S’assurer que `AnalysisWorker` utilise uniquement `callbacks['log']` pour ses messages (pas d’accès direct au GUI).

### 3.2 Nettoyage des logs “parallèles”

- [x] Rechercher dans `analyse_logic.py` et modules associés :
  - [x] toute écriture directe dans le log file,
  - [x] tout `print` ou logging “silencieux”.
- [x] Réorienter ces sorties vers les `callbacks` lorsque c’est pertinent.

---

## 🧲 Étape 4 — Boutons bas de fenêtre & markers

### 4.1 Mise à jour des boutons après analyse

- [x] Confirmer que `_on_results_ready` :
  - [x] appelle `set_results(results)` (ou équivalent) avant d’activer les boutons.
  - [x] appelle `self._update_buttons_after_analysis()`.
- [x] Dans `_update_buttons_after_analysis` vérifier :
  - [x] **Visualiser résultats** activé si `self._results_model` contient des lignes.
  - [x] **Appliquer recommandations** activé si des images sont marquées "kept/recommended".
  - [x] **Créer Stack Plan** activé si résultats présents.
  - [x] **Ouvrir log** activé si `log_path_edit` est non vide.
  - [x] **Gérer les marqueurs** délégué à `_update_marker_button_state()`.

### 4.2 Bouton "Gérer les marqueurs"

- [x] Vérifier que `_choose_input_folder` appelle bien `_update_marker_button_state()` après sélection.
- [x] Vérifier que `_has_markers_in_input_dir` :
  - [x] détecte `.astro_analyzer_run_complete` récursivement,
  - [x] exclut les dossiers de rejet (`snr_reject_dir`, `trail_reject_dir`) si `move_rejected=True`.
- [x] Après `manage_markers` :
  - [x] rappeler `_update_marker_button_state()` pour re-griser le bouton si nécessaire.

---

## 📊 Étape 5 — Visualisation & Stack Plan (sanity check)

> Le but ici est de s’assurer que ce qui existe déjà fonctionne avec la nouvelle chaîne d’analyse.

- [x] Lancer une analyse complète et cliquer sur **Visualiser résultats** :
  - [x] Les plots SNR/FWHM/scatter se basent bien sur les **nouvelles** données.
  - [x] L’onglet “Données détaillées” correspond à la table de l’onglet Results.
- [x] Cliquer sur **Créer un Stack Plan** :
  - [x] Le fichier CSV est bien généré.
  - [x] L’onglet stack plan se remplit comme dans la version Tk.
- [x] Vérifier que l’éventuelle gestion des recos dans la visualisation (sélection d’images) est cohérente avec les actions possibles dans l’onglet Results.

---

## 🧪 Étape 6 — Tests manuels finaux

### 6.1 Scénario “dossier sans markers”

- [ ] Choisir un dossier sans `.astro_analyzer_run_complete`.
- [ ] Vérifier que le bouton **Gérer les marqueurs** reste grisé avant et après analyse.

### 6.2 Scénario “dossier avec markers”

- [ ] Ajouter manuellement un fichier `.astro_analyzer_run_complete` dans un sous-dossier.
- [ ] Relancer le GUI et sélectionner ce dossier.
- [ ] Vérifier que le bouton **Gérer les marqueurs** est activé dès la sélection.

### 6.3 Scénario “grosse analyse”

- [ ] Lancer une analyse sur un dataset conséquent (plusieurs centaines d’images).
- [ ] Confirmer :
  - [ ] progression visible (barre + log),
  - [ ] pas de blocage du GUI (thread bien séparé),
  - [ ] log complet (fichier + fenêtre),
  - [ ] boutons et visualisation OK en fin de run.

---

## 🧷 Notes / questions à garder en tête

- [ ] Faut-il faire remonter **exactement** la même structure de résultats que Tk pour faciliter la parité complète des visualisations ?
- [ ] La logique de recommandations stack (percentiles SNR/FWHM/e/starcount) sera-t-elle gérée côté Qt ou réutilisera-t-on une fonction de `analyse_logic` ?
- [ ] Une fois tout ça stable, prévoir une étape séparée pour **parité parfaite de la fenêtre de visualisation** (onglet “Recommandations Stacking” identique au Tk).

---
