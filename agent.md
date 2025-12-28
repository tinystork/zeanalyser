# agent.md — ZeAnalyser (Qt) : File Organizer Seestar — EQ/ALTZ + LP/IRCUT (header-driven)

## Objectif
Ajouter un nouvel onglet **"Organizer"** (Qt / PySide6) pour trier un lot massif (ex: 20 000 FITS) provenant du Seestar
en créant une arborescence lisible basée UNIQUEMENT sur le header FITS (HDU0), sans lancer l’analyse.

Arborescence cible (par défaut) :
<INPUT_DIR>/_organized/
  EQ/
    IRCUT/
    LP/
    UNKNOWN_FILTER/
  ALTZ/
    IRCUT/
    LP/
    UNKNOWN_FILTER/
  NO_EQMODE/
    IRCUT/
    LP/
    UNKNOWN_FILTER/

Règle : si `EQMODE` est absent (ou indéterminable), on range dans `NO_EQMODE/*` (tri filtre quand même).

## Non-objectifs (important)
- Ne PAS modifier le pipeline d’analyse (analyse_logic, apply_pending_*, stack plan existant).
- Ne PAS modifier le bouton "Organiser fichiers" existant (celui des rejets/actions différées).
- L’Organizer doit fonctionner même si aucune analyse n’a été faite.

## Scope fichiers (strict)
- [x] **NOUVEAU** : `organizer_module.py` (backend pur, sans Qt)
- [x] **MODIF** : `analyse_gui_qt.py` (ajout onglet + câblage worker)
- [x] **MODIF** : `zone.py` (i18n fr/en : labels, messages)

⚠️ Ne toucher à rien d’autre.

---

## Spécification (basée sur ton header Seestar)

### Tags à lire (HDU0)
- `EQMODE` (int) : 1 = EQ, 0 = ALTZ
- `FILTER` (str) : ex 'IRCUT' ou 'LP' (ou autre)

Ton header type :
- `EQMODE  = 1`
- `FILTER  = 'IRCUT'`

### Classification mount-mode
- si `EQMODE` absent → `NO_EQMODE`
- sinon :
  - `int(EQMODE) == 1` → `EQ`
  - `int(EQMODE) == 0` → `ALTZ`
  - erreur conversion → `NO_EQMODE`

### Classification filtre
- si `FILTER` absent/empty → `UNKNOWN_FILTER`
- sinon normaliser : `val = str(FILTER).strip().upper()`
  - si `val` contient `IRCUT` → `IRCUT`
  - sinon si `val` contient `LP` → `LP`
  - sinon → `UNKNOWN_FILTER`

⚠️ On ne tente pas d’inventer d’autres filtres. Simple, stable.

---

## Règles de déplacement/copie (anti-casse)
- Par défaut : destination `<input_dir>/_organized`
- `Dry run` = ON par défaut : construit un plan + stats, sans modifier le disque.
- Mode : `Move` ou `Copy` (Move par défaut)
- Collisions : ne JAMAIS écraser. Si dst existe → suffixe `__01`, `__02`, etc.
- Anti-boucle : si `dest_root` est dans `input_dir`, ignorer tous fichiers déjà sous `dest_root`.
- Skip already organized = ON par défaut.

---

## Performance / lot massif
- Lire le header uniquement (pas de data)
- Utiliser `astropy.io.fits.getheader(path, 0)` (fiable)
- Scanner en `ThreadPoolExecutor` (IO bound)
  - `max_workers = min(8, os.cpu_count() or 4)`
- Vérifier `callbacks['is_cancelled']()` régulièrement (scan + apply).

---

## API backend (organizer_module.py)

### 1) Découverte fichiers
`iter_fits_files(input_dir, include_subfolders, skip_dirs_abs) -> list[str]`
- extensions : .fit/.fits (case-insensitive)
- ignore `dest_root` (skip_dirs_abs)

### 2) Lecture tags rapide
`read_seestar_tags(path) -> dict`
- retourne :
  - `eqmode_raw` (ou None)
  - `filter_raw` (ou None)
  - `error` (str) si header illisible

### 3) Classifs
`classify_mount(eqmode_raw) -> "EQ"|"ALTZ"|"NO_EQMODE"`
`classify_filter(filter_raw) -> "IRCUT"|"LP"|"UNKNOWN_FILTER"`

### 4) Planification
`build_plan(files, input_dir, dest_root, preserve_rel=False) -> (entries, summary)`
- `entries`: liste dict avec
  - `src_abs`, `dst_abs`, `mount_bucket`, `filter_bucket`, `status`
- `summary`: counts total + par buckets + erreurs

### 5) Application
`apply_plan(entries, move_files: bool, dry_run: bool, callbacks: dict) -> dict`
- applique move/copy
- collisions → suffixe
- cancel-safe
- retourne bilan : moved/copied/skipped/errors

---

## Intégration Qt (analyse_gui_qt.py)

### UI nouvel onglet "Organizer"
- Source folder (read-only) : reflète l’input du Project tab
- Destination folder : défaut `<input_dir>/_organized` + Browse
- Options :
  - include_subfolders
  - dry_run
  - move/copy (radio)
  - skip_already_organized
- Boutons :
  - Scan / Preview
  - Apply
  - Cancel
- Zone Summary (multi-lignes) : totaux + breakdown (EQ/ALTZ/NO_EQMODE) x (LP/IRCUT/UNKNOWN)

### Exécution thread
- Réutiliser `AnalysisWorker.start(analysis_callable=...)`
- 2 callables :
  - `_organizer_scan_callable(input_dir, dest_root, include_subfolders, skip, callbacks)`
    -> retourne `(entries, summary)`
  - `_organizer_apply_callable(entries, move_files, dry_run, callbacks)`
    -> retourne `apply_summary`

### UX guard rail (très important)
Après un APPLY (Move/Copy), afficher un message :
- “Les fichiers ont été déplacés/copés. Si vous aviez des résultats d’analyse affichés, ils peuvent référencer d’anciens chemins.
  Relancez une analyse en pointant sur le dossier _organized.”

⚠️ Ne pas auto-modifier le project path (disjoint), mais prévenir.

---

## i18n (zone.py)
Ajouter clés fr/en :
- [x] organizer_tab_title
- [x] organizer_source_label, organizer_dest_label
- [x] organizer_include_subfolders, organizer_dry_run
- [x] organizer_mode_move, organizer_mode_copy
- [x] organizer_skip_organized
- [x] organizer_scan_btn, organizer_apply_btn, organizer_cancel_btn
- [x] organizer_summary_title
- [x] organizer_scan_done, organizer_apply_done, organizer_error, organizer_warn_paths_invalid
- [x] organizer_paths_moved_warning

- [x] Mettre à jour `_retranslate_ui()` pour cet onglet.

---

## Critères d’acceptation
1) Avec ton header type : un fichier EQMODE=1 + FILTER=IRCUT va dans `EQ/IRCUT/`
2) Si EQMODE absent : va dans `NO_EQMODE/<filter>/`
3) Dry-run ne change rien sur disque.
4) Aucun écrasement en cas de collisions.
5) Pas de régression : analyse/organize existants inchangés.

---
### Nom des callbacks (côté organizer_module)
Dans la partie API backend, tu peux préciser :

Dans organizer_module, utiliser uniquement les callbacks
callbacks['status'], callbacks['progress'], callbacks['log'], callbacks['is_cancelled']
(noms alignés sur AnalysisWorker), et tester leur présence avec callbacks.get(...) avant appel.

Ça évite que Codex invente des noms exotiques du type update_progress.
