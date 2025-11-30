
# agent.md — ZeAnalyser Qt (analyse_gui_qt.py)

## 🎯 Mission

Finaliser l’intégration de l’interface Qt de ZeAnalyser V3 pour que :

1. L’analyse se lance via le vrai **`analyse_logic.perform_analysis`** (et plus seulement la simulation).
2. Le **log** soit correctement alimenté (fichier + zone texte Qt) en utilisant les callbacks existants.
3. Les **résultats complets** (SNR, FWHM, ECC, etc.) remontent bien dans l’onglet **Results**.
4. Les boutons bas de fenêtre (stack plan, markers, visualisation, recos…) réagissent correctement à la fin d’une analyse.
5. Le code reste **minimalement intrusif** vis-à-vis du reste du projet (Tk inclus).

> ⚠️ **Important :**  
> - Prends **cette version de `analyse_gui_qt.py` comme vérité absolue actuelle**.  
> - Tu dois **étendre/corriger** ce qui existe, pas réinventer une nouvelle fenêtre Qt.  
> - Ne change pas les noms des classes ni des méthodes publiques (`ZeAnalyserMainWindow`, `AnalysisWorker`, etc.).

---

## 📂 Fichiers à modifier

- `analyse_gui_qt.py` (principal)
- Éventuellement :
  - `analyse_logic.py` (adapter/ajuster `perform_analysis` et les fonctions de chargement de résultats si besoin)
  - `analysis_model.py` (si nécessaire pour exposer correctement les colonnes SNR/FWHM/ECC aux modèles Qt)
  - `stack_plan.py` (uniquement si besoin de compat pour la génération de stack plan, mais à éviter si possible)

Ne touche pas aux autres modules sauf nécessité démontrée.

---

## ✅ État actuel (à NE PAS casser)

À partir de la version fournie de `analyse_gui_qt.py` :contentReference[oaicite:0]{index=0} :

- `ZeAnalyserMainWindow` :
  - Gère déjà :
    - le choix du dossier d’entrée + remplissage auto de `analyse_resultats.log`,
    - l’écriture du fichier log via un `log_callback` construit dans `_start_analysis`,
    - la création d’un **`AnalysisWorker`** et le lancement via `w.start(...)`,
    - la connexion des signaux du worker via `_connect_worker_signals`,
    - la réception des résultats via `_on_results_ready` → `set_results(...)`,
    - l’onglet **Results** (table + filtres + tri SNR),
    - l’onglet **Stack Plan** et les fonctions `_create_stack_plan`, `_export_stack_plan_csv`, `_prepare_stacking_script`,
    - la gestion des **markers** (`_has_markers_in_input_dir`, `_manage_markers`, `_update_marker_button_state`),
    - la visualisation avec matplotlib (`_visualise_results`).
- `AnalysisWorker` :
  - Crée un thread Qt dédié, se branche sur `_on_thread_started`, et exécute soit :
    - un **callable d’analyse réel** (`analysis_callable`, ex: `analyse_logic.perform_analysis`),  
    - soit une **simulation** basée sur un timer (mode démo/dev).

Ces briques doivent être **réutilisées**, pas supprimées.

---

## 🧩 Plan de travail détaillé

### 1. Corriger et consolider `AnalysisWorker` (tick & callbacks)

#### [ ] 1.1. Corriger `_tick` dans `AnalysisWorker`

Actuellement, la méthode `_tick` de `AnalysisWorker` est manifestement un copié-collé de celle du `MainWindow` (elle utilise `self._progress_value`, `self.progress`, etc.), ce qui est faux dans le contexte du worker.

**À faire :**

- Réécrire `AnalysisWorker._tick` pour qu’il :
  - utilise **`self._progress`** (déjà présent dans le `__init__`) comme compteur interne,
  - émette `self.progressChanged.emit(...)` au lieu d’essayer de manipuler un QProgressBar,
  - émette éventuellement `self.logLine.emit(...)` pour quelques messages de debug,
  - lorsqu’il atteint 100%, stoppe son timer et émet `finished(False)` puis appelle `_clean_thread()`.

> En résumé : **dans `AnalysisWorker`, on n’accède jamais au GUI**, on ne fait qu’émettre des signaux.

#### [ ] 1.2. Vérifier `_run_analysis_callable`

- Garde la structure actuelle :

  ```python
  log_cb = kwargs.pop('log_callback', <default...>)
  callbacks = {
      'status': ...,
      'progress': ...,
      'log': log_cb,
      'is_cancelled': lambda: self._cancelled,
  }
  args = args + (callbacks,)
  result = analysis_callable(*args, **kwargs)
````

* L’objectif :
  `analyse_logic.perform_analysis(input_path, output_path, options, callbacks)` doit pouvoir :

  * appeler `callbacks['log'](text_key, **format_kwargs)` →
    ça passe par `log_callback` défini dans `_start_analysis`,
    qui :

    * traduit le message via `_translate`,
    * l’écrit dans le fichier log,
    * et fait `w.logLine.emit(full_text)`.

* S’assurer que :

  * `self.progressChanged.emit(100.0)` est bien appelé en fin de run,
  * `self.resultsReady.emit(result)` est bien émis si `result` est non-nul,
  * `self.finished.emit(bool(self._cancelled))` est toujours émis (même en cas d’erreur, où `error` est aussi émis).

---

### 2. Intégration avec `analyse_logic.perform_analysis` et résultats

#### [ ] 2.1. Vérifier/adapter la signature de `perform_analysis`

Dans `analyse_gui_qt.py`, on appelle :

```python
w.start(analyse_logic.perform_analysis, input_path, output_path, options, log_callback=log_callback)
```

et le worker ajoute `callbacks` à la fin des args.

Donc, côté `analyse_logic.py`, tu dois avoir quelque chose du genre :

```python
def perform_analysis(input_path, output_path, options, callbacks):
    # callbacks['status'](...)
    # callbacks['progress'](...)
    # callbacks['log']('some_key', **kwargs)
    # ...
    return results_list  # list[dict] avec snr, fwhm, ecc, etc.
```

Si la fonction actuelle ne retourne rien mais écrit seulement un CSV :

lui faire retourner la liste de dicts (sans casser l’usage Tk).
on reste cohérent avec Tk : la logique de parsing des résultats doit être factorisée dans `analyse_logic` ou `analysis_model`, pas recodée dans le GUI.

#### [ ] 2.2. Confirmer que SNR/FWHM/ECC apparaissent bien dans la table

* Vérifier que la liste de dicts retournée contient bien les clés :
  `snr`, `fwhm`, `ecc`, `sky_bg`, `sky_noise`, `signal_pixels`, `has_trails`, `num_trails`, `status`, `action`, etc.
* Vérifier que `AnalysisResultsModel` (dans `analysis_model.py`) expose ces colonnes et qu’elles sont bien indexées dans `self._keys`.
* La méthode `set_results` de Qt suppose :

  * que le modèle expose `_keys` et `_rows`,
  * que les données numériques sont accessibles en `Qt.UserRole` pour un tri SNR propre.

Si besoin, adapter `AnalysisResultsModel` mais sans casser le comportement Tk.

---

### 3. Log : s’assurer qu’il est toujours alimenté

Le schéma actuel dans `_start_analysis` est bon, il faut juste le respecter :

* `log_callback` :

  * traduit `text_key` via `_translate`,
  * préfixe par un timestamp `[HH:MM:SS]`,
  * écrit dans `log_file_path`,
  * et fait `w.logLine.emit(full_text)`.

#### [ ] 3.1. Vérifier que `perform_analysis` utilise exclusivement `callbacks['log']` pour ses messages

* Pas de `print` silencieux.
* Pas d’écriture directe dans le log ici : c’est `log_callback` qui s’en charge.
* S’il existe encore du code dans `analyse_logic` qui écrit lui-même dans le log, l’isoler / harmoniser avec ce schéma.

#### [ ] 3.2. Garder les messages de validation

Dans `_start_analysis`, il y a déjà un bloc qui valide les options lorsque `move_rejected=True` :

```python
debug_msg = f"DEBUG_VALIDATE: move_flag=..., detect_trails=..., snr_reject_dir=..."
self._log(debug_msg)
print(debug_msg)
...
```

* Conserver ce bloc mais :

  * si tu ajoutes des conditions d’erreur (ex: dossier absent), **loguer l’erreur à la fois dans le widget et dans le fichier** via `_log(...)` ou `log_callback`.

---

### 4. Boutons bas de fenêtre & markers

La mécanique est déjà bien avancée dans cette version, il faut juste la consolider.

#### [ ] 4.1. Vérifier l’activation des boutons après analyse

`_on_results_ready` appelle déjà :

```python
self.set_results(results)
self._update_buttons_after_analysis()
self._update_marker_button_state()
```

Dans `_update_buttons_after_analysis` :

* `visualise_results_btn` doit être activé si on a des résultats.
* `apply_recos_btn` activé s’il y a au moins un `r['recommended'] == True`.
* `manage_markers_btn` utilise `_update_marker_button_state()` → dépend de la présence de `.astro_analyzer_run_complete`.
* `open_log_btn` activé si `log_path_edit` non vide.
* `create_stack_plan_btn` activé si résultats présents.
* `send_save_ref_btn` activé si :

  * une “best reference” existe (via `_get_best_reference()`),
  * et le token parent est présent (`self.parent_token_available`).

**À faire :**

* S’assurer qu’une fois une analyse réelle terminée **et les résultats chargés** :

  * `_results_model` ou `_results_rows` est bien rempli avant l’appel à `_update_buttons_after_analysis`.
  * Sinon, déplacer/compléter l’appel à `_update_buttons_after_analysis` après le chargement final des résultats (ex : si tu lis le CSV dans `_on_worker_finished`).

#### [ ] 4.2. Markers : dégrisage automatique du bouton

La logique actuelle :

* `_choose_input_folder` :

  * met à jour `input_path_edit`, `log_path_edit`, `snr_reject_dir_edit`, `trail_reject_dir_edit`,
  * sauvegarde dans `QSettings`,
  * **appelle `_update_marker_button_state()`**.
* `_update_marker_button_state` :

  * appelle `_has_markers_in_input_dir`,
  * scan récursif de `input_dir` pour `.astro_analyzer_run_complete`,
  * **exclut les dossiers de rejet** si `move_rejected` est actif (via les radio buttons).

**À faire / vérifier :**

* À chaque fois que :

  * `input_path_edit` change,
  * `organize_files` a potentiellement modifié la structure,
  * `manage_markers` supprime des markers,

  → s’assurer que `_update_marker_button_state()` est bien rappelée.

Actuellement c’est déjà fait après `manage_markers` et dans `organize_files` (via `_update_marker_button_state()` indirectement). Juste vérifier que rien n’a été cassé.

---

### 5. Tests manuels à faire après implémentation

#### [ ] 5.1. Lancer une analyse réelle

1. Ouvrir `analyse_gui_qt.py` (`python analyse_gui_qt.py`).
2. Choisir un dossier de lights **déjà utilisé par la version Tk**.
3. Vérifier que :

   * `input_path_edit` se met à jour,
   * `log_path_edit` propose bien `.../analyse_resultats.log`,
   * les dossiers `rejected_low_snr` et `rejected_satellite_trails` sont suggérés.
4. Cliquer sur **Analyser** :

   * la barre de progression bouge,
   * des lignes arrivent dans la zone de log,
   * un fichier `analyse_resultats.log` est créé et rempli,
   * à la fin :

     * l’onglet **Results** contient les lignes,
     * SNR/FWHM/ECC sont visibles,
     * les boutons bas de fenêtre se dégrisent correctement.

#### [ ] 5.2. Markers

1. Dans le même dossier, vérifier qu’il existe des `.astro_analyzer_run_complete` (tu peux en créer un à la main).
2. Relancer le GUI, sélectionner ce dossier :

   * le bouton **Gérer les marqueurs** doit être **activé**.
3. Ouvrir la fenêtre de markers, tester :

   * suppression d’un marker sélectionné,
   * suppression de tous les markers,
   * fermeture de la fenêtre → bouton mis à jour (gris si plus de markers).

#### [ ] 5.3. Stack plan et visualisation

* Après une analyse, cliquer sur :

  * **Créer un stack plan** → CSV généré + onglet Stack Plan rempli.
  * **Visualiser les résultats** → fenêtres matplotlib avec SNR/FWHM/Scatter & tableau.

---

## ⚠️ Rappels / Contraintes

* Ne pas :

  * Renommer `ZeAnalyserMainWindow`, `AnalysisWorker`, `AnalysisRunnable`.
  * Modifier la signature publique de `main(...)`.
  * Toucher aux callbacks côté Tk : l’intégration Qt doit rester **un frontend parallèle**, pas un remplacement.
* Garder la logique de thread :

  * Le worker fait **tout** le travail lourd et n’accède jamais directement au GUI,
  * Le GUI ne fait que recevoir des signaux et rafraîchir ses widgets.

