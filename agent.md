✅ agent.md — Ajout d’un message de résumé « stack plan » dans le log du GUI

### 🎯 Mission

Quand un **stack plan** est généré à partir d’une analyse (ex : 30 fichiers analysés, 24 gardés), le GUI doit écrire dans le journal un message explicite de rappel, par exemple :

> `Plan d'empilement créé : 24 images sur 30 images analysées (80.0 %) -> stack_plan.csv`

Objectif : éviter de croire à un bug quand le CSV contient moins de lignes que le nombre de fichiers analysés (SNR / trails / filtres appliqués).

**Très important :**  
👉 *Ne pas modifier la logique d’analyse ni de génération du stack plan.*  
On ajoute **uniquement** de la **journalisation** (log) côté GUI.

---

### 📂 Fichiers concernés

- `analyse_gui.py`  
  - Contient la classe GUI principale (zone « Résultats / Journal » visible dans le screenshot).
  - Gère les callbacks de lancement d’analyse et de génération du stack plan.

- `analyse_logic.py`  
  - Contient la logique qui prépare les résultats d’analyse (liste d’images, statut, actions, etc.).
  - Fournit déjà le nombre total d’images **OK** et/ou analysées.

- `stack_plan.py`  
  - Contient la logique de création du plan d’empilement :
    - génération de la structure (lignes du plan)
    - écriture dans `stack_plan.csv`.

- (éventuellement) `ui_utils.py`
  - Si des helpers de log GUI existent déjà (par ex. fonction générique pour écrire dans le journal).

---

### 🧩 Comportement souhaité

1. **Moment du message**

   - Le message doit être écrit **immédiatement après** l’écriture du `stack_plan.csv` réussie.
   - Il doit apparaître dans la **zone de log du GUI** (même zone que :  
     `___ Analyse terminée ___` / `CSV pollution écrit: telescopes_pollution.csv` etc.).

2. **Contenu du message**

   À partir des données disponibles, calculer :

   - `total_ok_or_analysed` = nombre d’images **analysées et éligibles** avant filtrage SNR / trails,  
     ou, à défaut, **nombre de lignes « ok »** dans les résultats d’analyse.
   - `selected_for_stack` = nombre de lignes effectivement présentes dans le `stack_plan.csv`.
   - `pct = 100 * selected_for_stack / max(total_ok_or_analysed, 1)`.

   Puis logguer une ligne **en français** dans le GUI, par exemple :

   - Cas normal (au moins une image) :
     ```text
     Plan d'empilement créé : 24 image(s) sélectionnée(s) sur 30 images analysées (80.0 %) -> stack_plan.csv
     ```
   - Cas limite (aucune image éligible) :
     ```text
     Plan d'empilement créé : 0 image sélectionnée sur 30 images analysées (0.0 %) -> stack_plan.csv
     ```
   - Si pour une raison quelconque `total_ok_or_analysed` n’est pas disponible, fallback minimal :
     ```text
     Plan d'empilement créé : 24 entrée(s) dans stack_plan.csv
     ```

3. **Rappel pédagogique**

   Ajouter une petite phrase fixe rappelant que le stack plan ne contient que les images **retenues** :

   ```text
   Rappel : le plan d'empilement ne contient que les images retenues après filtrage (SNR / traînées / critères d'analyse).
Cette phrase peut être soit sur la même ligne que le résumé, soit sur la ligne suivante (au choix, mais lisible).

Robustesse

Ne pas crasher si :

le stack_plan.csv est vide ;

les statistiques d’analyse ne sont pas disponibles.

Le code doit simplement :

logguer ce qu’il sait ;

rester silencieux si la génération du stack plan a échoué ou été annulée.

🛠️ Plan de modification
Identifier le point d’entrée stack plan côté GUI

Dans analyse_gui.py, trouver le callback / handler qui :

appelle la logique de génération du stack plan (probablement via stack_plan.py) ;

sait où se trouve le dossier de travail et le chemin du stack_plan.csv.

Si la génération est déléguée à analyse_logic.py ou main_stacking_script.py, identifier la fonction de haut niveau qui :

reçoit les résultats d’analyse ;

produit le stack plan.

Récupérer les chiffres nécessaires

Récupérer, au même endroit :

selected_for_stack :
soit via la valeur de retour de write_stacking_plan_csv(...),
soit en calculant len(plan_rows) juste avant l’écriture du CSV.

total_ok_or_analysed :

idéalement à partir de la structure déjà utilisée pour le résumé d’analyse (celle qui donne par exemple :
Images initialement éligibles (OK): 30, Images sélectionnées / conservées par SNR : 24, etc.).

Si cette info est stockée dans un objet des résultats, l’exposer via un getter ou un simple champ.

Si ce n’est vraiment pas accessible, laisser tomber ce nombre et faire un message dégradé (voir plus haut).

Ajouter la fonction utilitaire de log (si besoin)

Si analyse_gui.py possède déjà une méthode dédiée au log (ex : append_log, log_message, write_to_log), la réutiliser.

Sinon, utiliser la même stratégie que les messages existants « Analyse terminée », « CSV pollution écrit: ... », etc.

Éviter de dupliquer la logique de formatage (timestamp, préfixe [INFO], etc.) : rester cohérent avec le reste du journal.

Écrire le message dans le GUI

Juste après le succès de la génération du stack_plan.csv, ajouter les appels de log :

Exemple pseudo-code (adapté au code réel par Codex) :

python
Copier le code
msg = (
    f"Plan d'empilement créé : "
    f"{selected_for_stack} image(s) sélectionnée(s)"
)
if total_ok_or_analysed is not None:
    pct = 100.0 * selected_for_stack / max(total_ok_or_analysed, 1)
    msg += f" sur {total_ok_or_analysed} images analysées ({pct:.1f} %)"
msg += f" -> {os.path.basename(stack_plan_path)}"

self.log_info(msg)  # ou méthode équivalente dans le GUI

self.log_info(
    "Rappel : le plan d'empilement ne contient que les images retenues après filtrage (SNR / traînées / critères d'analyse)."
)
Ne pas toucher à la logique métier

Ne jamais modifier :

les critères SNR / trails ;

la sélection des images ;

la structure du CSV (stack_plan.csv).

La mission est strictement de l’affichage / log.

✅ Tests attendus
Merci de prévoir au minimum :

Dataset de 30 fichiers (comme l’exemple fourni)

Lancer une analyse complète (SNR + génération automatique du stack plan).

Vérifier dans le journal GUI qu’apparaît par exemple :

text
Copier le code
Plan d'empilement créé : 24 image(s) sélectionnée(s) sur 30 images analysées (80.0 %) -> stack_plan.csv
Rappel : le plan d'empilement ne contient que les images retenues après filtrage (SNR / traînées / critères d'analyse).
Vérifier que le nombre 24 correspond bien au nombre de lignes dans stack_plan.csv.

Cas « 0 image retenue »

Forcer des critères SNR très stricts pour rejeter toutes les images.

Vérifier que :

la génération du stack plan ne plante pas (CSV vide ok) ;

un message clair est loggué (0 images sélectionnées).

Cas sans stack plan

Lancer une analyse sans demander de stack plan.

Vérifier qu’aucun message de type « Plan d’empilement créé » n’apparaît.

Non-régression

Vérifier que les autres messages du log (marqueur .astro_analyzer_run_complete, écriture de telescopes_pollution.csv, etc.) restent inchangés.

Vérifier qu’aucune nouvelle exception n’est levée en mode normal.