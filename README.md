# zeanalyser
Gui based Zesee Star Zenalalyser is a standalone analysis module for a lot of light, sorting and filtering ‘Lights’ files to discard low-quality frames and yield optimal star-field composites.available in Zeseestarstacker

## Platform support / Compatibilité

- **Windows, Linux et macOS** sont visés. macOS est validé automatiquement via GitHub Actions (runner `macos-latest`).
- Interfaces Tk et Qt fonctionnent en mode fenêtré classique ; pour un usage headless (CI), utilisez `QT_QPA_PLATFORM=offscreen` et `MPLBACKEND=Agg`.
- Les fonctions Bortle qui lisent des GeoTIFF/KMZ nécessitent l'optionnel `rasterio`. Si cette dépendance est absente, l'application affiche un message clair au lieu de planter.

## Installation / Installation

### PySide6 installation / Installation de PySide6

- **English**
  - Install PySide6 directly:

    ```bash
    pip install PySide6
    ```

  - Or install every dependency (PySide6 included) via the project requirements:

    ```bash
    pip install -r requirements.txt
    ```

  - Linux desktop requirements:
    - `libxcb-cursor0`
    - `xorg` / `x11-apps` if X11 utilities are missing
    - On WSL: use an X server such as **VcXsrv** or **Xming** and export your display, for example `export DISPLAY=localhost:0.0`.

- **Français**
  - Installez PySide6 directement :

    ```bash
    pip install PySide6
    ```

  - Ou installez toutes les dépendances (PySide6 inclus) depuis le fichier des dépendances :

    ```bash
    pip install -r requirements.txt
    ```

  - Prérequis Linux :
    - `libxcb-cursor0`
    - `xorg` / `x11-apps` si les utilitaires X11 manquent
    - Sous WSL : utilisez un serveur X comme **VcXsrv** ou **Xming** et exportez l'affichage, par exemple `export DISPLAY=localhost:0.0`.

> **Qt / xcb warning**
> 
> If you encounter the error `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`, install the missing X11 libraries and ensure the `QT_QPA_PLATFORM` environment variable points to an available display (on WSL, run `export DISPLAY=localhost:0.0`).

> **Avertissement Qt / xcb**
> 
> Si l'erreur `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` apparaît, installez les bibliothèques X11 manquantes et vérifiez que la variable d'environnement `QT_QPA_PLATFORM` pointe vers un affichage disponible (sous WSL, exécutez `export DISPLAY=localhost:0.0`).

### Usage / Utilisation

- **English**
  1. Create a virtual environment and activate it:

     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

  2. Install the required dependencies:

     ```bash
     pip install -r requirements.txt
     ```

  3. Launch the Tk interface (reference GUI):

     ```bash
     python analyse_gui.py
     ```

  4. Launch the Qt interface:

     ```bash
     python analyse_gui_qt.py
     ```

  For details on the result viewer interface, see [docs/visualisation.md](docs/visualisation.md).

- **Français**
  1. Créez un environnement virtuel et activez-le&nbsp;:

     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

  2. Installez les dépendances&nbsp;:

     ```bash
     pip install -r requirements.txt
     ```

  3. Lancez l'interface Tk (GUI de référence) :

     ```bash
     python analyse_gui.py
     ```

  4. Lancez l'interface Qt :

     ```bash
     python analyse_gui_qt.py
     ```

## Launch the Qt interface / Lancer l’interface Qt

```bash
python analyse_gui_qt.py
```

- **English**
  - **Input folder / Dossier d'entrée**: choose the directory containing your lights.
  - **Log file**: pick the corresponding log; when a folder is selected, the log path is auto-suggested.
  - **Analyse**: runs the standard analysis workflow.
  - **Analyse + Stack**: runs analysis and stacking when `token.zsss` is present.

- **Français**
  - **Dossier d'entrée** : choisissez le répertoire contenant vos images.
  - **Fichier log** : sélectionnez le log associé ; après choix du dossier, le chemin est auto-complété.
  - **Analyser** : lance le flux d'analyse standard.
  - **Analyser + Empiler** : lance l'analyse et l'empilement si `token.zsss` est présent.

## Interface language / Langue de l’interface

- **English**
  - Automatic detection (`auto`) chooses the best match from your system.
  - Manual selector offers **fr / en / auto** directly in the Qt GUI.
  - All strings come from `zone.py`, ensuring consistency across Tk and Qt.
  - The chosen language is stored via **QSettings** and restored on next launch.

- **Français**
  - La détection automatique (`auto`) suit la langue du système.
  - Le sélecteur propose **fr / en / auto** directement dans l'interface Qt.
  - Toutes les chaînes proviennent de `zone.py`, garantissant l'uniformité entre Tk et Qt.
  - La langue choisie est sauvegardée via **QSettings** puis restaurée au démarrage suivant.

## Appearance / Thème

- **English**
  - A dedicated tab exposes a **Dark Skin** option and **System Default**.
  - The chosen skin applies to the whole interface using Qt stylesheets or palettes.
  - Preferences persist through **QSettings**.

- **Français**
  - Un onglet dédié propose le mode **Dark Skin** et le **Système** par défaut.
  - Le thème s'applique à toute l'interface via une feuille de style ou palette Qt.
  - Les préférences sont conservées grâce à **QSettings**.

## Tk vs Qt overview / Différences Tk vs Qt

| Fonction / Feature            | Tk       | Qt                          |
| ----------------------------- | -------- | --------------------------- |
| Langue automatique            | ✔        | ✔                           |
| Mode sombre / Dark mode       | ✖        | ✔                           |
| Sauvegarde des préférences    | JSON     | QSettings                   |
| Visualisation                 | complète | en cours / work in progress |
| Stacking                      | intégré  | en cours / dépend token     |

## Linux / WSL tips / Astuces Linux et WSL

- **English**
  - Install key packages when Qt complains about X11 plugins:

    ```bash
    sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libx11-xcb1
    ```

  - On WSL, Wayland/Qt compatibility can be improved with:

    ```bash
    sudo apt install qtwayland5
    export QT_QPA_PLATFORM=xcb
    ```

- **Français**
  - Installez les paquets clés si Qt signale un plugin X11 manquant :

    ```bash
    sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libx11-xcb1
    ```

  - Sous WSL, la compatibilité Wayland/Qt peut être améliorée avec :

    ```bash
    sudo apt install qtwayland5
    export QT_QPA_PLATFORM=xcb
    ```

## macOS notes / Notes macOS

- Installez Python 3 depuis python.org ou Homebrew pour disposer des frameworks Tk et Qt.

### Known issues / Points d'attention

- **Optional Bortle maps / Cartes Bortle optionnelles** : `rasterio` repose sur GDAL. Si l'installation des roues échoue, installez GDAL via Homebrew (`brew install gdal`) ou désactivez cette fonctionnalité ; l'application affiche un message clair plutôt que de planter.
- **Headless usage / Mode sans affichage** : pour les environnements CI ou sans écran, forcez `QT_QPA_PLATFORM=offscreen` et `MPLBACKEND=Agg` afin d'éviter les erreurs liées à l'absence de serveur d'affichage.
- **Shell open helpers / Ouverture via le shell** : les actions qui ouvrent un dossier ou un fichier utilisent la commande `open`. Si macOS demande une autorisation d'accès au disque, acceptez-la pour permettre l'ouverture dans le Finder.
- Les dépendances principales (NumPy, Matplotlib, PySide6, rasterio) sont disponibles sous forme de roues binaires macOS ; installez-les via `pip install -r requirements.txt`.
- Les fonctions Bortle s'appuient sur `rasterio`. Si elle n'est pas installée, l'application signale clairement que cette fonctionnalité est indisponible plutôt que de planter.

## Pre-computed sky statistics reuse

The SNR analysis (`snr_module.calculate_snr`) already derives the sky
background (`sky_bg`) and noise (`sky_noise`). These values are now reused by
`starcount_module.calculate_starcount` and `ecc_module.calculate_fwhm_ecc` when
provided, preventing an extra call to `sigma_clipped_stats`. When invoking the
star count or FWHM helpers directly, pass the pre-computed statistics to skip
their internal estimation; both functions automatically fall back to a fresh
calculation if the supplied values are missing or non-finite.

**Français**

L'analyse SNR (`snr_module.calculate_snr`) dérive déjà le fond de ciel (`sky_bg`) et le bruit (`sky_noise`). Ces valeurs sont réutilisées par `starcount_module.calculate_starcount` et `ecc_module.calculate_fwhm_ecc` lorsqu'elles sont fournies, évitant un appel supplémentaire à `sigma_clipped_stats`. Si vous appelez ces fonctions directement, passez les statistiques pré-calculées pour contourner leur estimation interne ; les fonctions recalculent automatiquement si les valeurs sont absentes ou non finies.

## Bortle Classification

When using the helper functions in `bortle_utils.py`, make sure to convert
sky luminance expressed in **µcd/m²** to SQM (mag/arcsec²) before calling
`sqm_to_bortle`. The typical workflow is:

```python
l_ucd = sample_bortle_dataset(dataset, lon, lat)
sqm = ucd_to_sqm(l_ucd)
bortle_class = sqm_to_bortle(sqm)
```

Failing to perform the conversion will result in systematically obtaining a
Bortle class of 1, even with very bright skies.

The Bortle analysis relies on the dataset by:
Falchi, Fabio; Cinzano, Pierantonio; Duriscoe, Dan; Kyba, Christopher C. M.; Elvidge, Christopher D.; Baugh, Kimberly; Portnov, Boris; Rybnikova, Nataliya A.; Furgoni, Riccardo (2016): *Supplement to: The New World Atlas of Artificial Night Sky Brightness. V. 1.1.* GFZ Data Services. <https://doi.org/10.5880/GFZ.1.4.2016.001>
(study: <https://www.science.org/doi/10.1126/sciadv.1600377>). Download their raster to classify your data by Bortle.

L'analyse Bortle repose sur le jeu de données de :
Falchi, Fabio; Cinzano, Pierantonio; Duriscoe, Dan; Kyba, Christopher C. M.; Elvidge, Christopher D.; Baugh, Kimberly; Portnov, Boris; Rybnikova, Nataliya A.; Furgoni, Riccardo (2016) : *Supplement to: The New World Atlas of Artificial Night Sky Brightness. V. 1.1.* GFZ Data Services. <https://doi.org/10.5880/GFZ.1.4.2016.001>
(étude : <https://www.science.org/doi/10.1126/sciadv.1600377>). Il faut télécharger ce raster pour pouvoir classer les données par Bortle.


## Remerciements / Acknowledgments

**Français**

Je remercie chaleureusement **Astrobirder**, rencontré sur Discord, à l'origine de l'idée de classement par télescope et Bortle. Merci également aux concepteurs de toutes les bibliothèques utilisées dans ce projet. Vous pouvez l'utiliser en accord avec la licence, mais j'apprécierais d'être cité si mon travail vous sert de base.

**English**

Many thanks to **Astrobirder**, whom I met on Discord, for inspiring the idea of sorting by telescope and Bortle class. I also want to thank the authors of all the libraries used in this project. Feel free to use it in compliance with the license, but I would appreciate a citation if you reuse my work.

