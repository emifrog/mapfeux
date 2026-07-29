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
| [docs/strategie.md](docs/strategie.md) | Positionnement, périmètre, préalables juridiques, modèle économique, points d'arrêt. |
| [docs/plan-de-developpement.md](docs/plan-de-developpement.md) | **Avancement, jalons et prochaine action.** Source unique de l'état du projet. |
| [docs/adr/README.md](docs/adr/README.md) | Décisions d'architecture et écarts assumés au cahier. |

## État d'avancement

Fondations et couche territoriale du pilote livrées : monorepo, schéma Supabase,
socle web, worker Python, CI, carte et 316 communes sur le 06 et le 83. Reste
l'objet central du produit — la fiche événement — et l'ingestion FIRMS.

Le détail par jalon, les dettes et la prochaine action se trouvent dans le
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

#### Données de référence

Les migrations construisent le schéma ; le seed y verse le registre des sources
et les territoires d'amorçage. Sans lui, l'application fonctionne mais n'affiche
rien — `/statut` reste vide et aucun territoire n'est navigable.

```bash
micromamba run -n mapfeux-geo python scripts/apply-seed.py
```

Le script est idempotent et peut être rejoué. Le seed s'applique aussi à la main
depuis l'éditeur SQL du tableau de bord.

> **Piège sur `DATABASE_URL`.** Les mots de passe générés par Supabase
> contiennent souvent des caractères réservés d'URL. Un `@` non encodé décale la
> séparation utilisateur/hôte et produit une erreur de résolution DNS
> trompeuse — on croit à un problème réseau alors qu'il s'agit d'un format.
> Encoder le mot de passe en pourcent : `@` devient `%40`. Le script
> `apply-seed.py` le fait automatiquement.

### Ingestion planifiée — à faire une fois

La chaîne d'ingestion tourne toutes les dix minutes via GitHub Actions
(`.github/workflows/ingestion.yml`). Tant que ces trois étapes ne sont pas
faites, elle échoue à chaque déclenchement et la fraîcheur affichée sur le site
reste celle du dernier lancement manuel.

**1. Créer le rôle d'ingestion et lui poser un mot de passe.**

La migration `20260728160000_ingestion_role.sql` crée `mapfeux_ingest` avec les
seuls droits de la chaîne. Elle ne contient **aucun** mot de passe : une
migration est versionnée, donc publiée. Sans mot de passe, le rôle ne peut pas
s'authentifier — l'état par défaut est le plus sûr.

Après `pnpm db:push`, dans l'éditeur SQL du tableau de bord, avec une valeur
longue engendrée aléatoirement et jamais réutilisée :

```sql
alter role mapfeux_ingest password 'valeur-longue-et-aleatoire';
```

Le périmètre du rôle se contrôle à tout moment, sans rien modifier :

```bash
micromamba run -n mapfeux-geo python scripts/verify-ingestion-role.py
```

**2. Construire la chaîne de connexion du pooler.**

Tableau de bord → Connect → **Session pooler**. Prendre cette forme, et non la
connexion directe : celle-ci ne résout qu'en IPv6, dont les runners GitHub ne
disposent pas. Et le pooler en mode *transaction* (port 6543) casserait le
verrou d'exécution, qui est un verrou de session.

Dans la chaîne obtenue, remplacer `postgres.<ref>` par `mapfeux_ingest.<ref>` et
le mot de passe par celui posé à l'étape 1 :

```
postgresql://mapfeux_ingest.<ref>:<mot-de-passe>@aws-0-<région>.pooler.supabase.com:5432/postgres
```

**3. Déclarer les secrets du dépôt.**

Settings → Secrets and variables → Actions :

| Secret | Contenu |
|---|---|
| `INGESTION_DATABASE_URL` | la chaîne de l'étape 2 |
| `FIRMS_MAP_KEY` | la clé NASA FIRMS |

**4. Éprouver les identifiants avant de brancher l'ordonnanceur.**

Une tâche planifiée qui échoue sur un identifiant invalide échoue en silence
toutes les dix minutes : personne ne regarde un onglet Actions, et le site
continue d'afficher un âge de donnée qui grandit sans que rien ne le signale.

En ajoutant `INGESTION_DATABASE_URL` à `services/geo-worker/.env` — jamais
versionné — le contrôle porte sur exactement ce que la tâche utilisera :

```bash
micromamba run -n mapfeux-geo python scripts/check-credentials.py
```

Il vérifie la clé FIRMS auprès de la NASA, la connexion, le rôle obtenu, le
contournement RLS et surtout que **le verrou de session survit à une
validation** — le symptôme d'un pooler en mode transaction, qui laisserait deux
ingestions se superposer. Aucune valeur n'est affichée.

Puis déclencher une fois à la main — onglet Actions, workflow « Ingestion »,
*Run workflow* — pour vérifier avant d'attendre le créneau suivant.

> GitHub désactive les workflows planifiés après soixante jours sans activité
> sur le dépôt, et ne les déclenche que depuis la branche par défaut.

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
