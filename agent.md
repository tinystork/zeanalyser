# Mission – Fix Qt results visualisation labels + app icon

## Contexte

Projet : **ZeAnalyser / analyse_gui_qt.py** (GUI PySide6).

Deux problèmes purement cosmétiques ont été repérés dans la version actuelle :

1. Dans la fenêtre de visualisation des résultats (onglets SNR, FWHM, Eccentricity, Starcount, etc.),  
   le titre de la fenêtre et les labels de plage affichent les **clés i18n brutes** :

   - `_results_visualisation_title_`
   - `_visu_snr_range_label_`
   - `_visu_fwhm_range_label_`
   - `_visu_ecc_range_label_`
   - `_visu_starcount_range_label_`

   La cause : on utilise directement `_()` avec des clés qui n’existent pas et un paramètre `default=...`
   que l’implémentation de `_` **ignore**.  
   Le helper correct pour ce cas est **`_tr(key, fallback)`** défini dans `analyse_gui_qt.py`.

2. L’icône de l’application n’est pas appliquée dans le GUI Qt, alors que les fichiers suivants sont présents
   dans `zeanalyser/icon/` :

   - `zeanalyz_icon.png`
   - `zeanalyz_64x64.png`
   - `zeanalyz.ico`

   Il manque un petit helper qui charge ces fichiers et un appel à `app.setWindowIcon(...)` /
   `main_window.setWindowIcon(...)`.

Objectif : **corriger ces deux points dans `analyse_gui_qt.py` uniquement**, sans toucher au reste du code
(ni au GUI Tk).

---

## Fichiers à modifier

- `analyse_gui_qt.py` **uniquement**

---

## Étape 1 – Utiliser `_tr` pour la fenêtre de visualisation des résultats

1. Repérer les appels actuels à `results_visualisation_title` :

   - vers la fin du fichier, dans le code qui construit la fenêtre de visualisation (QDialog + QTabWidget).

   Exemple actuel (simplifié) :

   ```python
   dialog = QDialog(self)
   dialog.setWindowTitle(_("results_visualisation_title"))
````

2. Remplacer **tous** les `setWindowTitle(_("results_visualisation_title"))` par :

   ```python
   dialog = QDialog(self)
   dialog.setWindowTitle(_tr("results_visualisation_title", "Results visualisation"))
   ```

   * Ne pas changer le comportement de la fenêtre, seulement la façon de récupérer le texte.
   * Si la clé existe dans `translations`, `_tr` renverra la traduction.
     Sinon, on aura **au minimum** `"Results visualisation"` comme fallback.

---

## Étape 2 – Utiliser `_tr` pour les labels de plage SNR / FWHM / Ecc / Starcount

Dans la même fonction de visualisation des résultats (onglets SNR, FWHM, Eccentricity, Starcount) :

1. Repérer les labels du type `visu_*_range_label` qui ressemblent à ceci :

   ```python
   snr_range_label.setText(
       _(
           "visu_snr_range_label",
           default=f"SNR range: ({min_snr:.2f}, {max_snr:.2f})",
       )
   )
   ```

   et les callbacks `update_*_lines` qui font :

   ```python
   snr_range_label.setText(
       _(
           "visu_snr_range_label",
           default=f"SNR range: ({lo:.2f}, {hi:.2f})",
       )
   )
   ```

   Même pattern pour :

   * `"visu_fwhm_range_label"`
   * `"visu_ecc_range_label"`
   * `"visu_starcount_range_label"`

2. Remplacer **tous** ces appels par l’usage de `_tr` avec la chaîne complète en fallback, par exemple :

   ```python
   # SNR – initialisation
   snr_range_label.setText(_tr(
       "visu_snr_range_label",
       f"SNR range: ({min_snr:.2f}, {max_snr:.2f})",
   ))

   # SNR – callback on slider
   snr_range_label.setText(_tr(
       "visu_snr_range_label",
       f"SNR range: ({lo:.2f}, {hi:.2f})",
   ))
   ```

   Idem pour :

   ```python
   fwhm_range_label.setText(_tr(
       "visu_fwhm_range_label",
       f"FWHM range: ({...:.2f}, {...:.2f})",
   ))

   ecc_range_label.setText(_tr(
       "visu_ecc_range_label",
       f"Eccentricity range: ({...:.3f}, {...:.3f})",
   ))

   starcount_range_label.setText(_tr(
       "visu_starcount_range_label",
       f"Starcount range: ({...}, {...})",
   ))
   ```

   > **Important :**
   >
   > * Ne pas modifier la logique de mise à jour des lignes verticales ou des sliders.
   > * Ne pas changer les noms des clés (`visu_snr_range_label`, etc.).
   > * L’objectif est uniquement de remplacer l’appel à `_()` par `_tr()` avec une chaîne de fallback.

---

## Étape 3 – Ajouter un helper pour l’icône de l’application

1. En haut de `analyse_gui_qt.py`, après les imports Qt et les autres constantes globales,
   ajouter un helper qui construit le chemin vers le dossier `icon` relatif à ce fichier :

   ```python
   ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon")


   def get_app_icon() -> QIcon:
       """Return the best available application icon from the icon/ folder."""
       for name in ("zeanalyz_icon.png", "zeanalyz_64x64.png", "zeanalyz.ico"):
           path = os.path.join(ICON_DIR, name)
           if os.path.exists(path):
               return QIcon(path)
       return QIcon()
   ```

   Contraintes :

   * Utiliser `os.path` (pas besoin d’importer `pathlib`).
   * Garder `QIcon` (déjà importé plus haut).
   * Ne pas modifier d’autres constantes globales existantes.

---

## Étape 4 – Appliquer l’icône dans `main()`

Vers la fin du fichier, dans la fonction `main(argv: Optional[List[str]] = None)`, juste après la création de `app` :

```python
app = QApplication.instance() or QApplication(remaining_argv)
app.setOrganizationName("ZeSeestarStacker")
app.setApplicationName("ZeAnalyser")
```

1. Ajouter le chargement de l’icône :

   ```python
   app_icon = get_app_icon()
   if not app_icon.isNull():
       app.setWindowIcon(app_icon)
   ```

2. Après la création de la fenêtre principale :

   ```python
   win = ZeAnalyserMainWindow(
       command_file_path=None,
       initial_lang=args.lang,
       lock_language=args.lock_lang,
   )
   ```

   ajouter :

   ```python
   if not app_icon.isNull():
       win.setWindowIcon(app_icon)
   ```

3. Ne pas modifier le reste de la logique de `main` (gestion des args, `_show_window_safely`, etc.).

---

## Vérifications / Tests manuels

1. Lancer :

   ```bash
   python analyse_gui_qt.py
   ```

2. Ouvrir un fichier d’analyse permettant d’afficher la fenêtre de visualisation des résultats, puis vérifier :

   * Titre de la fenêtre : **plus de `_results_visualisation_title_`**, mais un libellé lisible
     (en anglais ou traduit si la clé existe).
   * En bas de chaque onglet SNR / FWHM / Eccentricity / Starcount :
     les labels affichent le texte lisible **avec les valeurs numériques**, sans `_visu_*_range_label_`.

3. Vérifier que l’icône :

   * Apparaît dans la barre de titre de la fenêtre principale.
   * Apparaît dans la barre des tâches (selon l’OS).

4. Lancer au moins avec `--lang fr` et `--lang en` pour s’assurer que `_tr` fonctionne proprement
   avec les traductions existantes, même si les clés ne sont pas encore ajoutées au dictionnaire.

