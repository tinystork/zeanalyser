
---

## `followup.md`

```markdown
# Suivi mission — Log de résumé du stack plan dans le GUI

Coche les cases au fur et à mesure pour suivre ce que Codex a fait.

## Implémentation

[x] Localiser dans `analyse_gui.py` (et/ou `analyse_logic.py`) l’endroit exact où :
  - le stack plan est généré ;
  - `stack_plan.csv` est écrit sur disque.

[x] Exposer ou récupérer, au moment de la génération du stack plan :
  - le nombre d’images analysées/éligibles (`total_ok_or_analysed`) ;
  - le nombre d’images sélectionnées pour le stack plan (`selected_for_stack`).

[x] Ajouter une petite fonction utilitaire ou réutiliser la méthode de log existante dans le GUI pour écrire des lignes d’info dans le journal « Résultats / Journal ».

[x] Après la génération réussie du `stack_plan.csv`, construire le message :

  - `Plan d'empilement créé : X image(s) sélectionnée(s) sur Y images analysées (Z %) -> stack_plan.csv`
  - Suivi d’un rappel :
    - `Rappel : le plan d'empilement ne contient que les images retenues après filtrage (SNR / traînées / critères d'analyse).`

[x] Gérer proprement les cas limites :
  - `total_ok_or_analysed` indisponible → message dégradé mais lisible ;
  - stack plan vide (0 image) → pas d’exception, message explicite ;
  - génération du stack plan échouée → ne rien logguer ou logguer une erreur, mais ne pas crasher le GUI.

[x] Vérifier que **rien n’est modifié** dans :
  - les critères de sélection SNR/traînées ;
  - la logique de génération du stack plan ;
  - la structure de `stack_plan.csv`.

[x] Tests unitaires automatiques ajoutés pour vérifier la présence et le format des messages de log (traductions + interpolation).

[ ] Lancer une analyse sur le dataset de 30 fichiers (exemple fourni) avec génération du stack plan, vérifier :
  - présence d’une ligne de log correcte avec X/Y et pourcentage ~80 % ;
  - cohérence de X avec le nombre de lignes dans `stack_plan.csv`.

[ ] Forcer un cas où 0 image est retenue :
  - stack plan généré sans planter ;
  - message de log compréhensible (0 sur N).

[ ] Lancer une analyse sans demander de stack plan :
  - aucun message « Plan d'empilement créé » ne doit apparaître.

[x] Confirmer qu’il n’y a aucune régression dans les autres messages de log ni dans le fonctionnement général du GUI. (tests unitaires OK)

