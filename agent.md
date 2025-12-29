# agent.md - Hotfix autoload Preview depuis Project (Qt)

## Objectif
Corriger le bug : quand l’utilisateur choisit un dossier dans l’onglet **Project** puis va dans **Preview**, la première image du dossier **doit** s’afficher automatiquement (sans “Open file”).

## Constat
Le viewer peut savoir autoload, mais `analyse_gui_qt.py` ne déclenche pas l’autoload au changement d’onglet (pas de wiring `QTabWidget.currentChanged` / pas d’appel `maybe_autoload_from_project_dir`).

## Périmètre STRICT
- Modifier uniquement `analyse_gui_qt.py`
- Ne pas modifier le comportement de l’onglet Project (browse, champs, logique existante)
- Ne pas toucher aux autres onglets (Results/Stack/Organizer/etc.)
- Aucune régression multi-OS (Windows/macOS/Linux)

## Tâches
- [x] **Identifier l’instance du QTabWidget principal**
  - c’est celui qui contient Project/Organizer/Results/Stack Plan/Preview/Settings.

- [x] **Connecter le signal de changement d’onglet**
  - Après la création des tabs et après avoir stocké `self.preview_tab_index`
  - Ajouter :
    - `self._main_tabs.currentChanged.connect(self._on_main_tab_changed)` (ou équivalent)
  - Le wiring doit être entouré d’un try/except pour rester safe en environnements partiels.

- [x] **Implémenter `_on_main_tab_changed(self, idx: int)`**
  - Si `idx != self.preview_tab_index` -> return
  - Lire `project_dir = (self.input_path_edit.text() or "").strip()`
  - Si `project_dir` vide ou non-dir -> return
  - Récupérer l’instance du viewer Preview (ex: `self.zeviewer`, `self.preview_viewer`, etc.)
    - Si introuvable -> return (ne pas crash)
  - Si le viewer expose `maybe_autoload_from_project_dir` -> l’appeler avec `project_dir`

- [x] **Gérer le cas “Preview onglet par défaut au démarrage”**
  - Ajouter un `QTimer.singleShot(0, ...)` qui appelle `_on_main_tab_changed(self._main_tabs.currentIndex())`
  - Safe guard try/except

## Verrous anti-régression
- Ne pas changer la logique de Project (juste lire `input_path_edit.text()`).
- Ne pas forcer de scan lourd dans `analyse_gui_qt.py` (tout est délégué au viewer).
- Aucune exception non gérée : tout le wiring doit être défensif.

## Définition de Done
- Choisir Input Folder dans Project -> switch Preview -> une image s’affiche sans “Open file”.
- Si aucun dossier Project -> switch Preview -> rien ne s’affiche, aucun crash.
- Aucun changement de comportement de Project.
