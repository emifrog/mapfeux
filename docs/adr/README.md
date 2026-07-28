# Décisions d'architecture

Registre des ADR du projet MapFeux. Cahier annexe F et §6.4.

Toute modification affectant le périmètre, la séparation public/opérationnel,
les sources de données, le modèle de panache ou l'exposition des schémas
Supabase doit être consignée ici et validée **avant** implémentation.

## Registre

| ADR | Sujet | Statut |
|---|---|---|
| ADR-001 | Choix Supabase / PostGIS comme source de vérité | à rédiger — décision actée au cahier §10.3 |
| ADR-002 | Worker Python séparé | à rédiger — décision actée au cahier §10.3 |
| ADR-003 | Schémas internes non exposés par la Data API | à rédiger — appliqué par `20260727120000_schemas_and_extensions.sql` |
| ADR-004 | Données brutes immuables | à rédiger — appliqué par `fire.detections.raw_payload` |
| ADR-005 | Stratégie cartographique | à rédiger |
| ADR-006 | Algorithme de regroupement | à rédiger — EPIC-04 |
| ADR-007 | Modèle de panache MVP | à rédiger — EPIC-06 |
| ADR-008 | Séparation DFCI OPS | à rédiger — décision actée au cahier §3.3 |
| ADR-009 | Stratégie de cache | à rédiger |
| ADR-010 | Politique de rétention | à rédiger |
| ADR-011 | Dimensions de statut et transitions autorisées | à rédiger — appliqué par `packages/domain/src/status-transitions.ts` et les contraintes de `fire.events` |
| ADR-012 | Provenance et chronologie | à rédiger |
| ADR-013 | Snapshots publics et mode dégradé | à rédiger |
| [ADR-014](014-environnement-sans-docker.md) | Environnement de développement et d'exécution sans Docker | accepté |
| [ADR-015](015-partitionnement-des-detections.md) | Partitionnement de `fire.detections` dès l'origine | accepté |
| [ADR-016](016-file-de-taches-postgresql.md) | File de tâches PostgreSQL au lieu de Celery et Redis | accepté, réversible |
| [ADR-017](017-source-des-limites-communales.md) | Source des limites communales pour le pilote | accepté, à réexaminer avant l'ouverture nationale |
| ADR-018 | Ordonnancement des tâches — réexamen d'ADR-016 | réservé, [décision ouverte](../strategie.md#81-ordonnancement--revenir-à-celery-et-redis) |
| ADR-019 | Tuiles vectorielles PMTiles, sans GeoJSON national en direct | réservé, à rédiger en J3 |
| ADR-020 | Hébergement en région UE, front et base, sous-traitants documentés | réservé |
| ADR-021 | Préfixe d'identifiant public, figé avant la première URL | réservé, [décision ouverte](../strategie.md#84-préfixe-didentifiant-public) |
| ADR-022 | Accessibilité : RGAA 4.1 niveau AA visé, déclaration publiée | réservé |
| ADR-023 | Politique de republication des informations officielles | réservé, à rédiger en J4 |

Les ADR 001 à 013 sont réservés par le cahier. Leur numérotation est figée ;
seul leur contenu reste à rédiger, au fur et à mesure des jalons qui les mettent
en œuvre.

Les numéros 018 à 023 sont réservés pour les décisions identifiées par la
[stratégie](../strategie.md). Un plan antérieur leur attribuait les numéros 014
à 017, déjà pris par des décisions acceptées et implémentées : la renumérotation
évite qu'un ADR en désigne deux choses différentes.

## Écarts au cahier v1.1 introduits par ces décisions

À reporter lors de la prochaine révision du cahier de développement :

1. **§11, §25.1, §25.4** — Docker et Docker Compose retirés (ADR-014).
2. **§10.2, §16.8** — Redis et Celery retirés du MVP (ADR-016).
3. **§12.4 et §13.5** — `fire.detections` est partitionnée dès l'origine, avec
   des clés composites (ADR-015).
4. **§11** — la racine du monorepo se nomme `mapfeux` et non `feux-de-france`.
5. **§13.6** — contrainte ajoutée : un `official_control_status` exige
   `verification_status = 'officially_confirmed'`. Publier « feu éteint » sur un
   simple regroupement algorithmique serait une affirmation non sourcée.
6. **§10.2** — Python 3.12 retenu plutôt que 3.13, pour la couverture binaire de
   la pile géospatiale. À réévaluer, sans urgence.
7. **Annexe C** — `SUPABASE_SERVICE_ROLE_KEY` renommée `SUPABASE_SECRET_KEY`.
   Supabase a remplacé la clé `service_role` au format JWT par une clé
   `sb_secret_…` ; la variable suit la terminologie du tableau de bord, sans
   quoi on y cherche une rubrique qui n'existe plus.
8. **§12.1** — l'exposition du schéma `api` n'est pas portée par
   `supabase/config.toml`, qui ne configure que le Supabase local. Sur un projet
   hébergé, elle se règle dans Project Settings → API → Exposed schemas. Le
   cahier ne le mentionnait pas.
9. **§9.5 et §16.7** — les limites communales du pilote proviennent de l'API
   Découpage administratif plutôt que des archives Géoplateforme (ADR-017). La
   version du COG n'est donc pas enregistrée.
