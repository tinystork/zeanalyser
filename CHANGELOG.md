# Changelog

## v3.5.0 – Fiabilisation et preuves de recherche (2026-10-02)

* Fiabilisation de l'aperçu, de la réouverture de projet et du chemin canonique des lignes de résultats
* Observables scientifiques robustes : comptage d'étoiles sans faux « zéro » sur erreur interne ; ECC calculé avec `eigvalsh` sur covariance symétrique (gardes physiques testées)
* Contrats documentaires v1 : états de résultat versionnés, format de corpus annoté et protocole de benchmark (schémas + exemples, sans image ni chemin privé)
* Réparation de l'intégration produit du détecteur de traînées satdet : unités de seuil, normalisation multi-extension et propagation fail-safe (aucun faux négatif sur erreur/absence)
* Séparation stricte des catégories de rejet : les recommandations déplacent les images hors sélection vers un dossier dédié `rejected_recommendations` (plus jamais fusionnées avec le rejet faible SNR) ; application SNR / traînées / recommandations isolées ; « Organiser » traite chaque catégorie vers sa destination propre sans double déplacement ; confirmation explicite avant application (annulation = zéro mutation) et persistance du log après action
* Spikes 001–003 inclus à titre de preuve de recherche uniquement : aucun backend sélectionné ni intégré ; le spike 003 (profil transverse) est publié avec verdict `PARTIAL`

## v3.4.0 – Project reopen and marker contract (2026-09-13)

* Restauration automatique des résultats persistés à l'ouverture d'un projet analysé, sans relancer l'analyse scientifique
* Nouveau marqueur atomique versionné `ZeAnalyser.marker.json`, écrit après finalisation de l'état réouvrable
* Compatibilité passive conservée avec `.astro_analyzer_run_complete` et gestion conjointe des deux générations
* Lecture en flux du dernier bloc de visualisation complet et valide, avec récupération après une fin de log corrompue

## v3.3.2 – Witness bump (2026-08-18)

* Incrément de version pour tests manuels (aucun changement fonctionnel)

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
