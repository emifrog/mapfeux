# Plan de développement MapFeux

**Dernière mise à jour** : 28 juillet 2026

Ce fichier est la **source unique de l'avancement** et le **seul** endroit où
vit le découpage en jalons.

| Document | Rôle |
|---|---|
| [Cahier de développement v1.1](../MapFeux_Cahier_de_developpement_v1.1.md) | Ce qu'il faut construire. Ne bouge qu'en révision. |
| [Stratégie](strategie.md) | Positionnement, périmètre, préalables, modèle économique, décisions ouvertes. Stable. |
| **Ce fichier** | Où l'on en est, ce qui reste, quelle est la prochaine action. Mis à jour à chaque session. |
| [Registre des ADR](adr/README.md) | Décisions techniques et écarts assumés au cahier. |

## Légende

| Marque | Sens |
|---|---|
| ✅ | Fait **et vérifié par exécution** |
| 🟢 | Fait, mais non exercé sur données réelles |
| 🟡 | En cours |
| ⬜ | À faire |
| ⚠️ | Point de vigilance ou dette assumée |

Un élément ne passe à ✅ que si quelque chose a réellement tourné : un test, un
build, une requête. « Le code est écrit » vaut 🟢, pas ✅.

---

## 1. Où en est le projet

**La chaîne complète répond**, vérifiée de bout en bout contre le projet
Supabase hébergé : navigateur → Next.js → PostgREST → schéma `api` → PostGIS.

**316 communes en base** — 163 dans les Alpes-Maritimes, 153 dans le Var. La
recherche trouve « Nice » comme « st etienne de tinee » sans accent ni tiret, un
point de Nice résout vers 06088, les fiches communales s'affichent.

**Aucune donnée d'observation n'a encore transité.** C'est le point dur du
moment : il manque la fiche événement, qui est l'objet central du produit
(§1 de la [stratégie](strategie.md)), et l'import FIRMS qui l'alimentera.

### Portes de qualité — dernier passage

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 40 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 17 fichiers |
| Worker | `mypy src` | ✅ strict, 12 fichiers |
| Worker | `pytest` | ✅ 39 tests |

---

## 2. Prochaine action

**Écrire la fiche événement `/evenements/[publicId]`**, alimentée par un jeu de
détections historiques importé à la main. C'est l'objet central du produit et
rien ne le bloque : le schéma, les règles de statut et les composants de
provenance sont en place depuis le lot de fondations.

Le critère de sortie est exigeant et volontairement vérifiable : **la fiche
s'affiche complètement avec JavaScript désactivé**, l'aperçu de partage est
correct, et aucun élément n'est affiché sans provenance ni horodatage.

En parallèle, de votre côté :

- ouvrir les préalables de la [phase 0](strategie.md#3-phase-0--préalables-non-techniques),
  en particulier l'autorisation de cumul — c'est un point d'arrêt du projet ;
- trancher les [décisions ouvertes](strategie.md#8-décisions-ouvertes), dont
  l'ordonnancement et le préfixe d'identifiant public ;
- `pnpm db:push` pour les deux migrations en attente
  (`20260727130000_api_municipalities.sql`,
  `20260728100000_source_status_freshness.sql`) ;
- `pnpm db:types` pour générer les types du schéma `api`.

---

## 3. Jalons

Hypothèse de charge : développement principalement solo, à temps partiel, en
parallèle d'un service de sapeur-pompier professionnel. Les durées sont en
**semaines calendaires**, pas en jours-homme.

| Jalon | Contenu | Estimé | Reste | État |
|---|---|---:|---:|---|
| J1 | Fondations et fiche événement sur données figées | 8 sem. | **5 sem.** | 🟡 fondations livrées |
| J2 | Ingestion FIRMS et regroupement réel | 6 sem. | 6 sem. | ⬜ normalisation déjà écrite |
| J3 | Carte et territoires | 6 sem. | **2 sem.** | 🟡 pilote livré |
| J4 | Informations officielles automatisées | 6 sem. | 6 sem. | ⬜ |
| J5 | Administration, supervision, mode dégradé | 5 sem. | 5 sem. | ⬜ |
| J6 | Recette, charge, sécurité, ouverture | 5 sem. | 5 sem. | ⬜ |
| | | 36 sem. | **29 sem.** | |

Les fondations et la couche territoriale du pilote étant livrées, il reste
**environ 29 semaines** au lieu de 36.

⚠️ Le phasage par rapport à la saison des feux est une
[décision ouverte](strategie.md#82-calendrier-et-saison) : les premiers jalons
tombent au moment où la disponibilité de l'auteur s'effondre, et une ouverture
au printemps ferait coïncider la première mise en charge réelle avec la première
crise majeure.

---

## 4. J1 — Fondations et fiche événement 🟡

Objectif : une page montrable très tôt, alimentée par un jeu de détections
historiques importé à la main.

### Livré ✅

- ✅ Monorepo pnpm/Turborepo, CI GitHub Actions, TypeScript strict, ruff et mypy
  strict côté Python
- ✅ Projet Supabase, dix schémas dont un seul exposé, grants révoqués par défaut
- ✅ Tables `events`, `detections`, `event_detections`, `event_history`,
  `event_timeline_entries`, `event_aliases`
- ✅ Contraintes en base sur les transitions de statut, dont l'interdiction faite
  aux traitements automatiques de renseigner un statut officiel (FR-047),
  doublée côté domaine — 12 tests
- ✅ `fire.detections` partitionnée dès l'origine ([ADR-015](adr/015-partitionnement-des-detections.md))
- ✅ Composants de statut, provenance et âge de donnée
- ✅ Vocabulaires contrôlés et formulations publiques obligatoires centralisés
- ✅ Dépôt publié : <https://github.com/emifrog/mapfeux>

### Reste ⬜

- ⬜ Route `/evenements/[publicId]` rendue côté serveur
- ⬜ Chronologie textuelle sur la fiche
- ⬜ Snapshot public par événement (§21.5)
- ⬜ Métadonnées de partage et aperçu social
- ⬜ Jeu de démonstration issu d'un feu historique du 06 ou du 83
- ⬜ Authentification administrateur
- ⚠️ Aucune politique RLS de lecture pour les administrateurs : l'administration
  passera par des appels serveur privilégiés (§14.2). À confirmer en J5.

**Critère de sortie** : la fiche s'affiche complètement avec JavaScript
désactivé, l'aperçu de partage est correct, aucun élément n'est affiché sans
provenance ni horodatage.

---

## 5. J2 — Ingestion FIRMS et regroupement ⬜

### Livré ✅

- ✅ Normalisation VIIRS et MODIS, clé d'idempotence, heures FIRMS sans zéro
  initial, rejet ligne à ligne — 23 tests
- ✅ Cycle de vie `import_run` (§16.1), exercé en conditions réelles par l'import
  des communes
- ✅ Environnement micromamba : ecCodes, GDAL, cfgrib, geopandas, rasterio

### Reste ⬜

- ⬜ Obtenir la clé FIRMS : <https://firms.modaps.eosdis.nasa.gov/api/map_key/>
- ⬜ Client HTTP avec gestion du quota (5 000 transactions / 10 min) et du 429
- ⬜ Découpage spatial de l'emprise France avec tampon frontalier
- ⬜ Archivage des fichiers bruts dans Storage avant tout parsing
- ⬜ Planification toutes les dix minutes
- ⬜ Algorithme de rattachement déterministe, paramètres externalisés (§17.2)
- ⬜ Calibration sur au moins trois saisons historiques du 06 et du 83
- ⬜ Score de fiabilité interne et seuils publics versionnés
- ⬜ Génération automatique et idempotente des entrées de chronologie (FR-058)
- ⬜ Fusion et séparation manuelles réversibles
- ⬜ `GET /api/v1/fires` avec bbox obligatoire au-delà du seuil national
- ⬜ ADR-006 et ADR-012 à rédiger
- ⚠️ L'ordonnanceur reste une [décision ouverte](strategie.md#81-ordonnancement--revenir-à-celery-et-redis).

**Critère de sortie** : rejouer une saison historique produit des événements
stables ; deux exécutions successives donnent le même résultat.

---

## 6. J3 — Carte et territoires 🟡

### Livré ✅

- ✅ Import des limites communales — 316 communes, aucun rejet
  ([ADR-017](adr/017-source-des-limites-communales.md))
- ✅ Staging, `ST_MakeValid`, `ST_CollectionExtract`, publication
  transactionnelle ; commune disparue datée et non supprimée (§13.2)
- ✅ Carte MapLibre, fond Géoplateforme IGN, attribution permanente — tuiles
  vérifiées dans un navigateur
- ✅ Recherche de commune : combobox ARIA, navigation clavier, annulation des
  requêtes obsolètes, dégradation explicite en cas de panne (FR-026)
- ✅ `GET /api/v1/territories`, `/municipalities/{insee}`, `/search`
- ✅ `POST /api/v1/location/resolve` — position en corps de requête et non en
  URL, car les URL atterrissent dans les journaux des CDN (§22.2)
- ✅ Pages `/carte`, `/territoire/[slug]`, `/commune/[insee]`, `/statut`
- ✅ Couche d'accès partagée : une page rendue serveur n'appelle pas sa propre
  API par HTTP

### Reste ⬜

- ⬜ **Génération PMTiles**, sans GeoJSON national servi en direct
- ⬜ Agrégation par département à l'échelle nationale (§21.3)
- ⬜ Géométries des régions et départements : seuls les quatre territoires du
  seed existent, avec un centre mais sans emprise
- ⬜ Import des 99 autres départements
- ⬜ Bouton « Autour de moi » — l'endpoint existe, le bouton reste à poser
- ⬜ Sélecteur de territoire groupé par région (FR-012)
- ⬜ Indicateurs de fraîcheur par couche
- ⚠️ `source_version` enregistre le fournisseur et la date d'import, pas un
  millésime COG officiel — assumé en ADR-017.

**Critère de sortie** : chargement initial sous 2,5 s en 4G sur mobile de
milieu de gamme ; la carte reste utilisable si FIRMS est indisponible.

---

## 7. J4 — Informations officielles ⬜

Le jalon différenciant. Capter automatiquement ce que publient les autorités,
sans jamais le réécrire.

- ✅ Modèle `app.official_messages` : organisme, URL source, date de publication,
  période de validité, territoire, événement lié, validateur
- ⬜ Connecteurs par type de source : flux RSS préfectoraux, pages de
  communiqués, vigilance Météo-France, arrêtés d'accès aux massifs
- ⬜ Rapprochement géographique entre une information officielle et un événement
- ⬜ Affichage strictement distinct des estimations automatiques (FR-104)
- ⬜ Gestion des contradictions entre observation satellitaire et statut officiel
- ⬜ ADR à rédiger sur la politique de republication
- ⚠️ La validation humaine avant publication est une
  [décision ouverte](strategie.md#83-validation-humaine-des-informations-officielles) :
  telle qu'écrite, elle annule le bénéfice de l'automatisation.

**Critère de sortie** : une information préfectorale publiée est visible sur la
fiche de l'événement correspondant en moins de 30 minutes, attribuée et datée,
sans réécriture.

---

## 8. J5 — Administration et exploitation ⬜

- ⬜ Authentification par lien magique, MFA obligatoire pour `super_admin`
- ⬜ `proxy.ts` pour le rafraîchissement de session
- ⬜ Tableau de bord de santé des sources
- ⬜ Gestion des événements : masquer, fusionner, séparer, classer en source
  thermique connue, corriger
- ⬜ Workflow d'information officielle attribuée, validé par un second regard
- ✅ Journal d'audit append-only, garanti par trigger
- ✅ Page `/statut` publique
- ⬜ Mode dégradé : timeouts, dernier snapshot valide, bannières explicites,
  aucun chargement indéfini (FR-115)
- ⬜ Observabilité : métriques, alertes sur retard d'import et snapshot ancien
- ⬜ Runbooks écrits pour les cinq pannes les plus probables (§23.4)
- ⚠️ Toute mutation exige un motif : la contrainte est en base, l'interface doit
  la respecter et non la contourner.

**Critère de sortie** : couper FIRMS, la météo et le réseau tour à tour ; le
site reste consultable et dit exactement ce qui manque et depuis quand.

---

## 9. J6 — Recette et ouverture ⬜

- ⬜ Tests E2E Playwright sur les parcours publics et administrateur
- ⬜ Tests de contrat fournisseur avec réponses figées
- ⬜ Tests géospatiaux : enclave, Corse, frontière maritime, point sur limite,
  proximité de Monaco (§24.3)
- ⬜ Test de charge : pic de crise, 200 000 visites/jour sur un département
- ⬜ **CSP avec nonces**, revue RLS, revue des fonctions `security definer`
- ⬜ Revue de sécurité indépendante
- ⬜ Audit RGAA 4.1 niveau AA et déclaration d'accessibilité
- ⬜ Pages légales, méthodologie, limites, confidentialité
- ⬜ Test de sauvegarde et de restauration
- ⬜ Checklist de mise en production (annexe G)
- ⬜ Ouverture progressive : 06 et 83, puis Sud-Est, puis national

---

## 10. Dettes et points de vigilance

| Sujet | Nature | Échéance |
|---|---|---|
| Préalables de phase 0 non engagés | Autorisation de cumul, cadre juridique — point d'arrêt | Immédiat |
| Décisions ouvertes non tranchées | Ordonnancement, calendrier, validation, préfixe | Avant J2 |
| CI jamais observée en vert | Premier déclenchement au commit initial | Immédiat |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | J1 |
| Pas de CSP | En-têtes partiels seulement | J6 |
| Aucun test de composant | Recherche et carte n'ont que le typage | J6 (Playwright) |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des jalons |
| Schémas `meteo`, `air`, `radar` vides | Tables reportées en v2 avec le panache | v2 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| Coût d'un pic non chiffré | Conditionne un point d'arrêt | Phase 0 |
| Réponse à la première erreur publique | Runbook éditorial absent | Avant J6 |

---

## 11. Tenue de ce fichier

À la fin de chaque session :

1. Mettre à jour la date en tête.
2. Faire passer les éléments terminés à 🟢, et à ✅ **seulement** après exécution.
3. Rafraîchir le tableau des portes de qualité si elles ont tourné.
4. Réécrire la section « Prochaine action » — elle ne doit contenir qu'une chose.
5. Ajouter toute dette nouvelle au tableau du §10 plutôt que de la laisser
   implicite dans le code.
6. Consigner dans [docs/adr/](adr/) tout écart au cahier, et l'ajouter à la liste
   du registre.

Le positionnement, le périmètre et les conditions d'arrêt ne se modifient pas
ici mais dans [strategie.md](strategie.md).

Une décision qui touche le périmètre, la séparation public/opérationnel, les
sources de données ou l'exposition des schémas Supabase passe par un ADR
**avant** implémentation, pas après.
