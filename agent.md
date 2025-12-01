
# agent.md — Réparer l’analyse + visualisation cassées depuis le commit `ce7242768d8ec17101dc063bcc84bb64c652ea40`

## 🎯 Objectif

Depuis le commit `ce7242768d8ec17101dc063bcc84bb64c652ea40`, l’analyse ZeAnalyser V3 côté GUI Qt ne se comporte plus correctement :

- le **log semble “vide”** dans le GUI (aucun résumé exploitable),
- la **visualisation** ne s’affiche plus (tableau et/ou graphiques),
- Codex tourne en rond quand on lui demande de “rétablir la fonction”.

Pourtant, un exemple de log réel (`analyse_resultats.log`) montre que le backend et le writer fonctionnent encore :

- entête “Début de l’analyse…”
- tableau “Analyse individuelle…”
- résumé “Résumé de l’analyse: …”
- bloc JSON entre  
  `--- BEGIN VISUALIZATION DATA ---`  
  et  
  `--- END VISUALIZATION DATA ---`.

👉 TA MISSION :  
**Rebrancher complètement la chaîne “fin d’analyse → log → JSON de visu → modèle Qt → tableau + boutons + graphiques” en Qt**, en recopiant fidèlement la logique de la version Tk qui fonctionne encore.

---

## 🗂️ Fichiers à considérer (SEULEMENT eux sauf nécessité absolue)

- `analyse_gui.py` (référence Tk **qui fonctionne**)
- `analyse_gui_qt.py` (GUI PySide6 actuel, buggué)
- `analysis_model.py` (modèle Qt des résultats)
- `analysis_schema.py` (schéma des lignes résultats / visualisation)
- `main_stacking_script.py` (lance l’analyse et écrit le log)

Ne touche pas aux modules lourds (snr, ecc, starcount, trails…) sauf si tu as une **preuve** qu’ils sont la cause directe de l’absence de résultats dans le GUI.

---

## ✅ Étape 1 – Comprendre le pipeline actuel

[X] 1.1. Dans `analyse_gui.py` (Tk), repérer **toute la chaîne** :

- où l’analyse est lancée,
- où le chemin du log est défini,
- quelle fonction lit le log et le JSON de visu (ex. `_load_visualization_data_from_log`),
- comment le tableau des résultats est rempli,
- comment les boutons de visu sont activés / désactivés.

[ ] 1.2. Dans `analyse_gui_qt.py`, repérer les équivalents :

- slot qui lance l’analyse (bouton “Analyser”),
- comment le log path est construit (généralement `.../analyse_resultats.log`),
- fonction de recharge : `_load_visualisation_from_log_path(log_path: str)`,
- méthode qui remplit le modèle Qt : `set_results(...)`,
- gestion des boutons : `_update_buttons_after_analysis()`, `_update_marker_button_state()`, etc.,
- méthode de visu : `_visualise_results()`.

[ ] 1.3. Vérifier que **le backend** (dans `main_stacking_script.py`) écrit bien :

- le tableau “Analyse individuelle…”,
- le **résumé** “Résumé de l’analyse”,
- et surtout le bloc JSON complet entre `--- BEGIN VISUALIZATION DATA ---` et `--- END VISUALIZATION DATA ---`.

> ⚠️ Ne change pas le format du log ni les marqueurs : ils sont déjà consommés par Tk et par d’anciens scripts.

---

## ✅ Étape 2 – S’aligner sur la logique Tk pour la lecture du log

[ ] 2.1. Ouvrir dans `analyse_gui.py` la fonction qui lit le bloc de visualisation (nom proche de `_load_visualization_data_from_log`).

[ ] 2.2. **Comprendre exactement** ce que fait cette fonction :

- comment elle cherche **le dernier** `--- END VISUALIZATION DATA ---`,
- comment elle remonte jusqu’au `--- BEGIN VISUALIZATION DATA ---` précédent,
- comment elle agrège les lignes JSON entre ces deux marqueurs,
- comment elle gère les cas d’erreur (pas de marqueurs, JSON vide, JSON invalide).

[ ] 2.3. Dans `analyse_gui_qt.py`, **faire en sorte que** `_load_visualisation_from_log_path(log_path)` :

- utilise **le même algorithme** pour localiser la section JSON (avec les mêmes marqueurs),
- parse le JSON et remplit `self.analysis_results` avec une **liste de dict**,
- **appelle** ensuite :

  - `self.set_results(self.analysis_results)`  
  - puis, si possible, `self._compute_recommended_subset()`  
  - puis met à jour l’état des boutons : `_update_buttons_after_analysis()` et `_update_marker_button_state()`.

⚠️ Ne “réinvente” pas un autre parsing : **copie la logique Tk**, adapte juste au style Qt (méthodes / attributs).

---

## ✅ Étape 3 – S’assurer que le log path est correct et exploité

[ ] 3.1. Vérifier dans `analyse_gui_qt.py` :

- la construction de `self.log_path_edit` et `_suggest_log_path(input_dir)`,
- le comportement de `_choose_input_folder()` : après sélection d’un dossier d’entrée, `log_path_edit` doit automatiquement pointer vers `input_dir/analyse_resultats.log`, comme en Tk.

[ ] 3.2. Vérifier que lors d’un lancement via CLI (`python analyse_gui_qt.py -i D:\ASTRO\lights`), le `main()` :

- remplit `input_path_edit` **et**
- appelle `_suggest_log_path()` pour initialiser `log_path_edit`.

[ ] 3.3. Vérifier dans le slot de fin d’analyse (callback du worker Qt) que :

- `self.log_path_edit` contient bien le chemin du log qui vient d’être écrit,
- si `self.analysis_results` est vide après le run, le code appelle :

  ```python
  log_path = self.log_path_edit.text().strip()
  if log_path and os.path.isfile(log_path):
      self._load_visualisation_from_log_path(log_path)
````

* et que cette séquence n’est **pas** court-circuitée par un `return` prématuré.

---

## ✅ Étape 4 – Modèle Qt & remplissage du tableau

[ ] 4.1. Dans `analysis_model.py`, vérifier quelles clés sont attendues dans chaque `row` (par ex. `file`, `status`, `snr`, `background`, `noise`, `pixsig`, `starcount`, `fwhm`, `ecc`, etc.).

[ ] 4.2. Comparer ces clés avec celles présentes dans le JSON du log (fichier fourni `analyse_resultats.log`).

* Si certaines colonnes sont optionnelles (ex. `starcount`, `fwhm`, `ecc` pour ce run), le modèle doit gérer les valeurs `None` sans planter.
* Ne change pas la structure du JSON si la version Tk la consomme déjà correctement.

[ ] 4.3. Vérifier que `set_results(rows)` :

* stocke bien `rows` dans le modèle (`AnalysisResultsModel`),
* met à jour le `QTableView` via `QSortFilterProxyModel`,
* rafraîchit les entêtes de colonnes et permet le tri.

---

## ✅ Étape 5 – Visualisation (dialogue & graphes)

[ ] 5.1. Dans `_visualise_results()` :

* s’assurer que, si `self.analysis_results` est vide mais `log_path` est défini, la fonction appelle bien `_load_visualisation_from_log_path(log_path)` **avant** de conclure “No results to visualise”.
* après rechargement, `rows` doit être basé sur le modèle Qt (`_results_model._rows`) ou directement sur `self.analysis_results`.

[ ] 5.2. Vérifier que :

* si `matplotlib` n’est pas dispo → fallback texte (stats) fonctionne,
* si `matplotlib` est dispo → les onglets (SNR, FWHM, Ecc, Traînées, Données brutes) utilisent bien les colonnes disponibles.

⚠️ IMPORTANT : même si SNR/FWHM/ECC sont `None` dans ce log de test, la fenêtre de visu ne doit pas “planter silencieusement” → elle doit au minimum afficher un onglet “Données brutes” avec la liste des fichiers.

---

## ✅ Étape 6 – Tests rapides obligatoires

[ ] 6.1. À partir du log fourni (`analyse_resultats.log`), écrire dans `analyse_gui_qt.py` **un petit test manuel** (si possible dans un `if __name__ == "__main__":` de debug ou un test unitaire séparé) :

* instancier `ZeAnalyserMainWindow`,
* appeler `_load_visualisation_from_log_path(path_du_log_exemple)`,
* vérifier que `len(self.analysis_results) == 30` (pour ce log),
* vérifier qu’au moins une ligne a `status == "ok"`.

[ ] 6.2. Lancer l’UI Qt, charger un dossier d’entrée et lancer une analyse réelle :

* vérifier que le log sur disque contient bien le bloc JSON de visu,
* cliquer sur “Visualiser les résultats” et s’assurer que :

  * le tableau de résultats est rempli,
  * les boutons de visu/stack sont activés comme en Tk,
  * si les données sont pauvres (pas de SNR/FWHM/ECC), au moins les données brutes sont visibles.

---

## 🧱 Règles de conduite

* **Ne change pas** le format du log ni du JSON de visualisation.
* **Ne touche pas** au backend d’analyse (snr/ecc/starcount/trails…) tant que le problème GUI n’est pas clairement identifié.
* Si tu dois adapter un morceau du code Tk → **copie la logique** et adapte seulement l’API Qt (widgets, signaux).
* Pas de refactor massif, pas de renommage gratuit : le but est de **réparer** rapidement, pas de tout réorganiser.

---

## ✅ Critère de réussite

* À partir d’un run réel :

  * un fichier `analyse_resultats.log` est bien généré avec la section `--- BEGIN/END VISUALIZATION DATA ---`,
  * `ZeAnalyserMainWindow` (Qt) :

    * recharge ce log,
    * remplit le tableau des résultats,
    * permet d’ouvrir la fenêtre de visualisation,
    * et, au minimum, affiche la liste des 30 fichiers du log fourni.

* Le comportement est **équivalent** à la version Tk (`analyse_gui.py`) pour les mêmes entrées/logs.

