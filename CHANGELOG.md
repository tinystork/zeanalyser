# Changelog

## v3.3.1 – Standalone closure (2026-08-17)

* `acstools` devient une dépendance runtime obligatoire (détection de traînées satellite)
* Restauration de l'identité/icône Windows dans la taskbar (AppUserModelID `ZeSoftware.ZeAnalyser`)
* Documentation du lancement standalone packagé (`zeanalyser` / `python -m zeanalyser`)

## v3.x.x – Migration progressive vers Qt

### Nouveautés

* Introduction du GUI **analyse_gui_qt.py**
* Support natif **PySide6 / Qt6**
* Détection automatique de langue + sélecteur manuel
* Ajout de l’onglet **Apparence / Skin** (Dark Mode + System)
* Nouveau système de préférences via **QSettings**
* Meilleure gestion du fichier log (auto-suggestion, validation)
* Support du Bortle via sélection GeoTIFF / KMZ
* Nouveau moteur de tri et filtrage avancé (SNR, FWHM, ECC, trails)
* Préparation du futur système de prévisualisation FITS

### Corrections

* Correction du crash lorsque le plugin Qt "xcb" est manquant
* Auto-génération du chemin du fichier log si dossier sélectionné
* Correction du comportement des boutons "Visualiser", "Ouvrir log"

### Obsolescence programmée

* Le GUI Tkinter reste disponible mais ne recevra plus que des patchs mineurs
* Le projet migre progressivement vers **ZeAnalyser V3 – Qt**
