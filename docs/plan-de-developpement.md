# Plan de développement MapFeux

**Dernière mise à jour** : 27 juillet 2026
**Référence fonctionnelle** : [MapFeux_Cahier_de_developpement_v1.1.md](../MapFeux_Cahier_de_developpement_v1.1.md)
**Écarts assumés au cahier** : [docs/adr/README.md](adr/README.md)

Ce fichier est la **source unique de l'avancement**. Le cahier décrit ce qu'il
faut construire et ne bouge qu'en révision ; ce plan décrit où l'on en est et se
met à jour à chaque session de travail.

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

**Lot 0/1 terminé.** Le socle technique tient : monorepo, schéma de base
complet pour les détections et les événements, application web qui construit,
worker Python dont la pile géospatiale fonctionne sous Windows sans Docker.

**Lot 2 : la moitié web est en place**, la moitié données ne l'est pas. Les
pages territoriales, la recherche de commune, la carte et les endpoints
existent et se construisent, mais `geo.municipalities` est vide. Les pages
territoire fonctionnent grâce au seed — France, PACA, 06, 83 ; les pages
commune répondront 404 jusqu'à l'import IGN.

**Aucune donnée réelle n'a encore transité.** C'est le point dur du moment.

### Portes de qualité — dernier passage

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 40 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 12 fichiers |
| Worker | `mypy src` | ✅ strict, 10 fichiers |
| Worker | `pytest` | ✅ 23 tests |

### Jalons du cahier §26.3

| Jalon | Contenu | État |
|---|---|---|
| — | Fondations : monorepo, Supabase, CI | ✅ |
| A | Carte territoriale : France, départements, communes, recherche | ⬜ |
| B | Détections FIRMS visualisées sur 06 et 83 | ⬜ |
| C | Événements : regroupement, provenance, chronologie, admin | ⬜ |
| D | Panache indicatif reproductible | ⬜ |
| E | MVP pilote : CAMS, radar, statut, PWA, supervision | ⬜ |
| F | Ouverture nationale : charge, sécurité, communication | ⬜ |

---

## 2. Prochaine action

**Exposer le schéma `api` sur le projet Supabase hébergé.** Toutes les requêtes
échouent aujourd'hui avec `PGRST106: Invalid schema: api`, constaté en exécutant
l'application.

> Project Settings → API → **Exposed schemas** → ajouter `api`

`supabase/config.toml` ne configure que le Supabase local ; sur un projet
hébergé, cette liste se règle dans le tableau de bord. Conserver `public` et
`graphql_public`, n'ajouter que `api` — aucun schéma interne ne doit y figurer
(§12.1).

Ensuite, vérifier :

```bash
pnpm dev
# http://localhost:3000/api/v1/status      → sourceCount 5, status "degraded"
# http://localhost:3000/statut             → les cinq sources en « Indisponible »
# http://localhost:3000/territoire/alpes-maritimes → carte centrée sur le 06
pnpm db:types                              # types du schéma api, aujourd'hui absents
```

Les cinq sources doivent apparaître en `unavailable` : aucun import n'a jamais
tourné, c'est le résultat attendu.

Puis **écrire l'import IGN ADMIN EXPRESS**, seul verrou restant du lot 2 : sans
communes en base, la recherche ne renvoie rien, les pages commune répondent 404
et le lot 3 n'aura nulle part où rattacher les détections.

Et si la CI n'est pas encore verte : <https://github.com/emifrog/mapfeux/actions>.

---

## 3. Lot 0/1 — Fondations ✅

### Monorepo et outillage ✅

- ✅ pnpm workspace + Turborepo, Node 22
- ✅ TypeScript strict — `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`
- ✅ ESLint flat config, Prettier
- ✅ `.gitattributes`, `.gitignore`, `.env.example`
- ✅ Dépôt publié : <https://github.com/emifrog/mapfeux> — commit initial `aca4d4b`,
  104 fichiers
- 🟢 CI GitHub Actions : trois jobs — web, worker (micromamba), migrations sur
  PostGIS vierge
- ⚠️ **La CI n'a encore jamais été observée en vert.** Le job `migrations` est le
  plus exposé : il rejoue les neuf migrations sur une base vide après avoir
  reconstitué à la main l'environnement Supabase — rôles `anon`,
  `authenticated`, `service_role`, schéma `auth` et `auth.uid()` factice.
  Première exécution en échec, diagnostiquée et corrigée : l'image
  `postgis/postgis` pré-installe PostGIS dans `public`, ce qui transformait
  `create extension if not exists postgis with schema extensions` en no-op
  silencieux. Le préambule remet désormais la base dans l'état d'un projet
  Supabase neuf, et une étape de contrôle échoue lisiblement si ce n'était pas
  le cas. À reconfirmer en vert.

### `packages/domain` ✅

- ✅ Vocabulaires contrôlés, alignés sur l'annexe D du cahier
- ✅ Règles de transition de statut — 12 tests, dont le refus qu'un job écrive un
  statut officiel (FR-047)
- ✅ Calcul de fraîcheur source et événement — 11 tests
- ✅ Formulations publiques obligatoires (§22.5) centralisées

### `packages/contracts` 🟢

- ✅ Enveloppe `{ data, meta }`, codes d'erreur de l'annexe E
- ✅ Validation bbox avec plafond de surface — 8 tests
- 🟢 Schémas `fires`, `territories` écrits, non encore consommés par un endpoint

### `packages/ui` et `packages/map-style` 🟢

- 🟢 `cn`, libellés publics, `ProvenanceBadge`, `DataAge`
- 🟢 Palette §8.2, symboles, paliers de zoom §21.3 — 3 tests sur les paliers
- ⬜ Aucun composant n'est encore monté dans une page réelle

### Base de données 🟢

Neuf migrations appliquées sur le projet Supabase hébergé.

- ✅ Dix schémas, un seul exposé (`api`), grants révoqués par défaut
- ✅ `app.territories`, `geo.municipalities` avec index trigramme
- ✅ `ingest.data_sources`, `import_runs`, `incidents`
- ✅ `fire.detections` partitionnée dès l'origine ([ADR-015](adr/015-partitionnement-des-detections.md))
- ✅ `fire.events` avec contraintes d'attribution des statuts officiels
- ✅ `fire.event_detections`, `event_history`, `event_timeline_entries`, `event_aliases`
- ✅ `admin.profiles`, `audit.entries` append-only par trigger
- ✅ Vues et fonctions `api.*`, seed des cinq sources et des territoires 06/83
- ⚠️ **Les schémas `meteo`, `air` et `radar` sont créés mais vides.** Leurs tables
  (§13.12 à §13.18) arrivent avec les lots 5 et 6.
- ⚠️ **Aucune politique RLS de lecture pour les administrateurs.** L'administration
  passera par des appels serveur en `service_role`, conformément au §14.2. À
  confirmer au lot 9.

### `apps/web` 🟢

- ✅ Build Next 16, en-têtes de sécurité, `Permissions-Policy` autorisant la
  géolocalisation sur notre seule origine
- 🟢 Layout avec bandeau de positionnement permanent et pied de page légal
- 🟢 Accueil, page `/statut` rendue serveur
- 🟢 `GET /api/v1/status`, `GET /api/v1/municipalities/search`
- 🟢 Clients Supabase serveur et navigateur, limités au schéma `api`
- ⚠️ **Pas de CSP.** Elle exige des nonces via `proxy.ts` ; posée à moitié avec
  `unsafe-inline`, elle donnerait une fausse assurance. Traitée au lot 10.
- ⬜ Types de base générés (`pnpm db:types`)

### `services/geo-worker` ✅

- ✅ Environnement micromamba — ecCodes 2.48.0, GDAL, cfgrib, geopandas, rasterio
  vérifiés à l'import sous Windows
- ✅ Connecteur FIRMS : normalisation VIIRS et MODIS, clé d'idempotence, heures
  FIRMS sans zéro initial, rejet ligne à ligne — 23 tests
- ✅ Journalisation JSON expurgeant clés, payloads et coordonnées
- ✅ Service HTTP interne : `/health`, `/readiness` déclarant les connecteurs sans clé
- 🟢 Interfaces fournisseurs génériques (§30.1)
- 🟢 Cycle de vie `import_run` (§16.1) — écrit, jamais exécuté contre une base
- ⬜ File de tâches PostgreSQL et planification APScheduler ([ADR-016](adr/016-file-de-taches-postgresql.md))

### Documentation 🟡

- ✅ ADR-014, ADR-015, ADR-016 rédigés
- ✅ Registre des ADR et liste des six écarts au cahier v1.1
- ⬜ ADR-001 à ADR-013 : numérotation réservée, contenu à rédiger au fil des lots
- ⬜ Runbooks (§23.4)

---

## 4. Lot 2 — Territoires et carte 🟡

**Jalon A.** Durée indicative : 2 semaines. EPIC-02.

### Import des référentiels ⬜ — **le verrou**

- ⬜ Connecteur Géoplateforme IGN, en respectant la limite de 10 requêtes/seconde
- ⬜ Import ADMIN EXPRESS COG : régions, départements, communes
- ⬜ Staging, `ST_MakeValid`, comparaison de version, publication transactionnelle
- ⬜ Géométries simplifiées par palier de zoom, génération PMTiles
- ⚠️ Import manuel et contrôlé, pas de job fréquent : ce référentiel change deux
  fois par an

### API 🟢

- ✅ Migration `api.municipalities` — vue sans géométrie, les limites passeront
  par les tuiles vectorielles (§21.1)
- 🟢 `GET /api/v1/territories` et `/territories/{slug}` avec liens officiels
- 🟢 `GET /api/v1/municipalities/{insee}` et `/search`
- 🟢 `POST /api/v1/location/resolve` — position transmise en corps de requête et
  non en URL, car les URL atterrissent dans les journaux des CDN (§22.2)
- ✅ Couche d'accès partagée entre pages et endpoints : une page rendue serveur
  n'appelle pas sa propre API par HTTP

### Interface 🟢

- 🟢 Carte MapLibre, fond Géoplateforme IGN avec attribution permanente
- 🟢 Recherche de commune : combobox ARIA, navigation clavier, annulation des
  requêtes obsolètes, dégradation explicite en cas de panne (FR-026)
- 🟢 Pages `/carte`, `/territoire/[slug]`, `/commune/[insee]`
- 🟢 Accueil listant les territoires ouverts
- ⬜ Sélecteur de territoire groupé par région (FR-012)
- ⬜ « Autour de moi » — l'endpoint existe, le bouton reste à poser
- ⚠️ **Le fond IGN n'a jamais été chargé dans un navigateur.** L'URL WMTS de la
  Géoplateforme est construite d'après la convention documentée, mais rien ne
  l'a confirmée contre le service réel. Si les tuiles ne s'affichent pas,
  regarder d'abord `packages/map-style/src/basemap.ts` — `MAP_STYLE_URL` permet
  d'y substituer un autre fond sans toucher au code.

**Fin de lot** : la France est navigable, les communes cherchables, sans aucune
donnée temps réel.

---

## 5. Lot 3 — Détections FIRMS ⬜

**Jalon B.** Durée indicative : 2 semaines. EPIC-03.

- ⬜ Obtenir la clé FIRMS et la placer dans l'environnement du worker
- ⬜ Client HTTP avec gestion du quota (5 000 transactions / 10 min) et du 429
- ⬜ Découpage spatial de l'emprise France avec tampon frontalier
- ⬜ Archivage des fichiers bruts dans Storage avant tout parsing
- ⬜ Insertion idempotente — la normalisation est déjà écrite et testée
- ⬜ Planification toutes les 10 minutes
- ⬜ `GET /api/v1/fires` avec bbox obligatoire au-delà du seuil national
- ⬜ Affichage des détections, différenciation visuelle par ancienneté
- ⬜ Légende et avertissement « centre de pixel » (FR-035)
- ⬜ Page `/sources` avec les attributions

**Fin de lot** : les détections réelles du 06 et du 83 sont visibles et datées.

---

## 6. Lot 4 — Événements ⬜

**Jalon C.** Durée indicative : 2 à 3 semaines. EPIC-04. **Cœur du produit.**

- ⬜ Algorithme de rattachement déterministe (§17.2)
- ⬜ Calibrer les paramètres sur un corpus historique : distance de base 2–3 km,
  extension +0,5 km/h, fenêtre 18–24 h
- ⬜ Score de fiabilité interne, exposé en trois niveaux seulement
- ⬜ Génération de la chronologie, idempotente et versionnée (FR-058)
- ⬜ Snapshot public par événement (§21.5)
- ⬜ Fiche `/evenements/[publicId]` rendue serveur, lisible avant la carte
- ⬜ `GET /api/v1/fires/{publicId}`, `/detections`, `/timeline`
- ⬜ Redirection des identifiants fusionnés via `api.resolve_event_alias`
- ⬜ Administration : fusion, séparation, masquage motivé, source thermique connue
- ⬜ ADR-006 et ADR-012 à rédiger
- ⚠️ Les règles de transition sont déjà codées et testées des deux côtés. Ce lot
  les **branche**, il ne les réinvente pas.

**Fin de lot** : le regroupement est validé sur des cas historiques connus.

---

## 7. Lot 5 — AROME et panache ⬜

**Jalon D.** Durée indicative : 3 à 4 semaines. EPIC-05 et EPIC-06.
**Chemin critique du projet.**

- ⬜ Tables `meteo.model_runs`, `wind_samples`, `smoke_forecasts`, `smoke_steps`,
  `affected_municipalities`
- ⬜ Adaptateur catalogue Météo-France — la migration des portails est annoncée,
  l'endpoint doit pouvoir changer sans toucher au métier
- ⬜ Téléchargement GRIB2, extraction U/V à 10 m, interpolation
- ⬜ Algorithme de panache v1 (§18.3), paramètres versionnés
- ⬜ Garde-fous : vitesse aberrante, distance et surface maximales, `ST_IsValid`,
  désactivation globale immédiate
- ⬜ Intersection PostGIS avec les communes, tri par heure estimée d'arrivée
- ⬜ Score d'incertitude, rendu MapLibre en contour pointillé
- ⬜ Page `/methodologie` expliquant honnêtement les limites
- ⬜ ADR-007 à rédiger
- ⚠️ Le relief du 06 dégrade fortement la pertinence du modèle. L'incertitude doit
  être visible, pas discrète.

---

## 8. Lot 6 — CAMS et radar ⬜

Durée indicative : 2 à 3 semaines. EPIC-07 et EPIC-08.

- ⬜ Tables `air.model_runs`, `air.grid_assets`, `radar.frames`
- ⬜ Client CAMS, import PM2,5 et PM10, génération de COG et tuiles
- ⬜ Publication atomique, conservation de la version précédente
- ⬜ Valeur par commune avec mention « donnée modélisée »
- ⬜ Connecteur radar, timeline, animation limitée à 24 frames
- ⬜ Rétention courte et purge automatique
- ⬜ Vérifier qu'une panne CAMS ou radar ne bloque pas la carte FIRMS

---

## 9. Lot 7 — PWA, accessibilité et contenus ⬜

Durée indicative : 2 semaines. EPIC-10 partiel.

- ⬜ Manifeste, service worker, cache limité au shell et aux pages statiques
- ⬜ Bannière hors connexion — jamais de donnée de cache présentée comme fraîche
- ⬜ Alternative textuelle synchronisée avec l'emprise (§8.6)
- ⬜ Audit RGAA des parcours principaux, navigation clavier, contrastes
- ⬜ Pages `/a-propos`, `/mentions-legales`, `/confidentialite`, `/accessibilite`
- ⬜ Vérifier qu'aucun écran ne reste en chargement indéfini (FR-115)

---

## 10. Lot 8 — Administration ⬜

Durée indicative : 2 semaines. EPIC-09.

- ⬜ Authentification par lien magique, MFA obligatoire pour `super_admin`
- ⬜ `proxy.ts` pour le rafraîchissement de session
- ⬜ Tableau de bord de santé des sources
- ⬜ Gestion des territoires et des liens officiels
- ⬜ Workflow d'information officielle attribuée, avec validation par un second regard
- ⬜ Journal d'audit consultable
- ⚠️ Toute mutation exige un motif : la contrainte est déjà en base sur
  `audit.entries`, l'interface doit la respecter et non la contourner.

---

## 11. Lot 9 — Supervision, sécurité et recette ⬜

Durée indicative : 2 à 3 semaines. EPIC-10.

- ⬜ CSP avec nonces, complète cette fois
- ⬜ Métriques, alertes, tableaux d'exploitation
- ⬜ Tests E2E Playwright (§24.5)
- ⬜ Tests géospatiaux : enclave, Corse, frontière maritime, point sur limite,
  proximité de Monaco (§24.3)
- ⬜ Tests de charge : vue nationale en pic, 10 000 points, 100 panaches simultanés
- ⬜ Test de pénétration ciblé
- ⬜ Runbooks (§23.4), dont « fausse détection médiatisée »
- ⬜ Test de sauvegarde et de restauration
- ⬜ Checklist de mise en production (annexe G)

---

## 12. Dettes et points de vigilance

| Sujet | Nature | Échéance |
|---|---|---|
| Schéma `api` non exposé | `PGRST106` sur toutes les requêtes | Immédiat |
| CI jamais observée en vert | Premier déclenchement au commit initial | Immédiat |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | Lot 2 |
| Fond IGN jamais chargé | URL WMTS construite d'après la doc, non vérifiée | Lot 2 |
| Aucun test de composant | La recherche et la carte n'ont que le typage | Lot 9 (Playwright) |
| Pas de CSP | En-têtes partiels seulement | Lot 9 |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des lots |
| Schémas `meteo`, `air`, `radar` vides | Tables à créer | Lots 5 et 6 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| `import_run` jamais exécuté | Code non exercé contre une base | Lot 3 |
| Marque « MapFeux » non validée | Antériorités et domaines à vérifier | Avant le jalon F |
| Coût d'hébergement non chiffré | Absent du cahier | Avant le jalon E |

---

## 13. Tenue de ce fichier

À la fin de chaque session de travail :

1. Mettre à jour la date en tête.
2. Faire passer les éléments terminés à 🟢, et à ✅ **seulement** après exécution.
3. Rafraîchir le tableau des portes de qualité si elles ont tourné.
4. Réécrire la section « Prochaine action » — elle ne doit contenir qu'une chose.
5. Ajouter toute dette nouvelle au tableau du §12 plutôt que de la laisser
   implicite dans le code.
6. Consigner dans [docs/adr/](adr/) tout écart au cahier, et l'ajouter à la liste
   des écarts du registre.

Une décision qui modifie le périmètre, la séparation public/opérationnel, les
sources de données, le modèle de panache ou l'exposition des schémas Supabase
passe par un ADR **avant** implémentation, pas après.
