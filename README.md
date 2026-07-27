# MapFeux

Plateforme publique de suivi des détections thermiques, des feux potentiels et
des fumées.

> **Positionnement.** Service d'information cartographique grand public,
> indépendant de tout dispositif opérationnel. Ni système d'alerte, ni source de
> confirmation terrain, ni outil de commandement. Les consignes et publications
> des autorités restent prioritaires.

| Document | Rôle |
|---|---|
| [MapFeux_Cahier_de_developpement_v1.1.md](MapFeux_Cahier_de_developpement_v1.1.md) | Référence fonctionnelle. Ne bouge qu'en révision. |
| [docs/plan-de-developpement.md](docs/plan-de-developpement.md) | **Avancement et prochaine action.** Source unique de l'état du projet. |
| [docs/adr/README.md](docs/adr/README.md) | Décisions d'architecture et écarts assumés au cahier. |

## État d'avancement

Lot 0/1 terminé : monorepo, schéma Supabase, socle web, worker Python et CI.
Aucune donnée réelle n'a encore transité — c'est l'objet des lots 2 et 3.

Le détail, les dettes et la prochaine action se trouvent dans le
[plan de développement](docs/plan-de-developpement.md), tenu à jour à chaque
session. Ce README ne duplique pas ce suivi.

## Structure

```text
mapfeux/
├── apps/web/               Next.js 16 — public et administration
├── services/geo-worker/    FastAPI, ingestion et calculs géospatiaux
├── packages/
│   ├── domain/             vocabulaires, règles de statut, fraîcheur
│   ├── contracts/          schémas Zod de l'API v1
│   ├── ui/                 composants et libellés partagés
│   ├── map-style/          palette, symboles, stratégie de zoom
│   └── config/             tsconfig et ESLint partagés
├── supabase/
│   ├── migrations/         schéma, RLS et surface publique `api`
│   └── seed/               registre des sources, territoires d'amorçage
├── docs/adr/               décisions d'architecture
└── .github/workflows/      intégration continue
```

## Prérequis

- **Node.js 22.11+** et **pnpm 11+**
- **micromamba** pour le worker Python — voir
  [services/geo-worker/README.md](services/geo-worker/README.md)
- Un **projet Supabase hébergé** de développement

Docker n'est pas utilisé : voir
[ADR-014](docs/adr/014-environnement-sans-docker.md).

## Démarrage

```bash
pnpm install
cp .env.example apps/web/.env.local   # renseigner les valeurs Supabase
pnpm dev
```

Le fichier d'environnement doit se trouver dans `apps/web/`, pas à la racine :
Next.js ne remonte pas l'arborescence du monorepo pour le chercher.

### Base de données

#### Exposer le schéma `api` — à faire une fois par projet

**Sans cette étape, toutes les requêtes échouent avec `PGRST106: Invalid
schema: api`.**

Le fichier `supabase/config.toml` ne configure que le Supabase **local**. Sur un
projet hébergé, les schémas exposés par la Data API se règlent dans le tableau
de bord :

> Project Settings → API → **Exposed schemas** → ajouter `api`

Conserver `public` et `graphql_public` dans la liste. Le schéma `api` est le
seul schéma métier exposé ; `app`, `geo`, `fire`, `meteo`, `air`, `radar`,
`ingest`, `admin` et `audit` ne doivent jamais y figurer (cahier §12.1).

#### Migrations

Les migrations sont l'unique moyen de modifier le schéma. Elles s'appliquent au
projet Supabase hébergé sans Docker :

```bash
pnpm dlx supabase login
pnpm dlx supabase link --project-ref <ref-du-projet>
pnpm db:push        # applique supabase/migrations dans l'ordre
pnpm db:types       # régénère les types TypeScript du schéma api
```

Le seed (`supabase/seed/`) s'applique une fois, à la main, depuis l'éditeur SQL
du tableau de bord ou avec `psql`.

## Commandes

| Commande | Effet |
|---|---|
| `pnpm dev` | Serveur de développement |
| `pnpm build` | Construction de production |
| `pnpm lint` | ESLint sur tous les paquets |
| `pnpm typecheck` | TypeScript strict |
| `pnpm test` | Tests unitaires |
| `pnpm format` | Prettier |

## Règles de contribution

- Le schéma de production ne se modifie **que** par migration versionnée.
- Aucune logique métier critique ne vit uniquement dans l'interface.
- Toute formulation publique nouvelle passe par
  `packages/domain/src/disclaimers.ts` ou `packages/ui/src/labels.ts`, et par
  une validation métier.
- Une détection satellitaire n'est **jamais** présentée comme une confirmation
  officielle : les trois dimensions de statut restent séparées.

## Attributions

Données NASA FIRMS, Météo-France (AROME, radar), Copernicus CAMS et IGN
(ADMIN EXPRESS COG). Les attributions détaillées sont portées par la table
`ingest.data_sources` et publiées sur la page `/sources`.
