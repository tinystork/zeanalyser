# followup.md - Validation Hotfix autoload Preview

- [ ] **Cas 1 - Autoload OK**
  - Lancer l’app
  - Onglet Project : choisir un dossier avec des images (fit/fits/png)
  - Aller sur Preview
  - Attendu : la première image apparaît automatiquement.

- [ ] **Cas 2 - Pas de Project folder**
  - Lancer l’app
  - Ne rien choisir dans Project
  - Aller Preview
  - Attendu : rien ne charge, aucun crash.

- [ ] **Cas 3 - Preview par défaut (si applicable)**
  - Configurer l’app pour démarrer sur Preview (ou simuler via code)
  - Attendu : autoload se déclenche via QTimer.singleShot.

- [ ] **Cas 4 - Non-régression Project**
  - Browse, include_subfolders, log path, boutons Analyse/Organize : inchangés.
