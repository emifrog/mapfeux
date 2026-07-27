# ADR-015 — Partitionnement de `fire.detections` dès l'origine

- **Statut** : accepté
- **Date** : 2026-07-27
- **Corrige** : une contradiction entre le cahier §12.4 et §13.5

## Contexte

Le cahier décrit deux exigences incompatibles en l'état :

- §12.4 : « `fire.detections` partitionnée mensuellement par `acquired_at`
  lorsque la volumétrie le justifie » ;
- §13.5 et annexe A : `id uuid PK` et `provider_key text unique`.

PostgreSQL impose que **la clé de partitionnement figure dans toute contrainte
d'unicité** d'une table partitionnée. Une table créée avec `primary key (id)` et
`unique (provider_key)` ne peut donc pas être partitionnée par `acquired_at`
sans réécrire ses deux contraintes.

Cette réécriture, différée jusqu'au moment où « la volumétrie le justifie »,
tomberait précisément au pire moment : sur une table de plusieurs millions de
lignes, en pleine saison, sous verrou exclusif.

## Décision

`fire.detections` est créée **partitionnée par plage sur `acquired_at` dès la
première migration**, avec :

- `primary key (id, acquired_at)` ;
- `unique (provider_key, acquired_at)` ;
- des partitions mensuelles créées à l'avance par
  `fire.ensure_detection_partition(date)` ;
- une partition `DEFAULT` filet de sécurité, qui doit rester vide.

L'unicité reste sémantiquement correcte : `provider_key` est un hash qui encode
déjà l'heure d'acquisition (§17.1), donc deux lignes de même `provider_key` ont
nécessairement le même `acquired_at`. La clé composite n'affaiblit pas la
garantie d'idempotence de FR-033.

## Conséquences

- Le coût est nul à faible volumétrie et la migration douloureuse est évitée.
- Toute table référençant une détection doit reprendre les deux colonnes :
  `fire.event_detections` porte `(detection_id, detection_acquired_at)`.
- Une tâche planifiée doit créer les partitions à venir. Si elle échoue, les
  lignes atterrissent dans la partition `DEFAULT` sans perte, mais l'ajout d'une
  partition ultérieure devient coûteux : la présence de lignes dans `DEFAULT`
  doit être surveillée.
- La rétention se fait par `DETACH PARTITION`, quasi instantané, au lieu d'un
  `DELETE` massif.

## Mise à jour du cahier

Le §12.4 et le §13.5 doivent être corrigés : le partitionnement n'est pas
conditionnel, et les clés de `fire.detections` sont composites.
