# ADR-014 — Environnement de développement et d'exécution sans Docker

- **Statut** : accepté
- **Date** : 2026-07-27
- **Remplace** : la mention de Docker et Docker Compose au cahier §11, §25.1 et §25.4

## Contexte

Le cahier de développement v1.1 prévoyait Docker à trois endroits : le répertoire
`infra/docker` et `infra/compose` du monorepo, l'environnement local décrit au
§25.1, et l'hébergement du worker au §25.4. Le porteur du projet a exclu Docker
de la chaîne de développement.

Trois dépendances reposaient sur cette brique :

1. **Supabase en local** — `supabase start` lance des conteneurs, sans
   alternative native.
2. **Redis** — aucun build natif Windows officiel.
3. **La pile géospatiale** — GDAL et surtout **ecCodes**, nécessaire à la lecture
   des GRIB2 AROME, n'ont pas de roue PyPI fiable sur Windows. C'était le motif
   principal du conteneur.

## Décision

**Développement de la base** : contre un projet Supabase hébergé dédié. Le CLI
Supabase reste utilisé pour `db push`, `db diff` et `gen types`, qui ne
requièrent pas Docker. Il est installé en dépendance npm du monorepo, sans
installation globale.

**Environnement Python** : un environnement conda-forge géré par **micromamba**,
décrit dans `services/geo-worker/environment.yml`. conda-forge fournit des
binaires win-64 pour ecCodes, GDAL, cfgrib et rasterio. C'est le remplacement
direct de l'image Docker géospatiale, et le seul moyen d'obtenir ecCodes sur
Windows sans compilation.

**File de tâches** : voir [ADR-016](016-file-de-taches-postgresql.md). Redis est
retiré du MVP, ce qui supprime la deuxième dépendance au conteneur.

**Production** : Next.js sur Vercel, inchangé. Le worker tourne sur un VPS avec
systemd et un environnement micromamba, déployé par `git pull` et redémarrage de
service, au lieu d'un déploiement d'image.

## Conséquences

**Favorables**

- Une dépendance lourde en moins sur le poste de développement.
- L'environnement de dev pointe vers un vrai Supabase : les politiques RLS,
  Auth et Storage sont testées telles qu'elles seront en production, ce qu'un
  Supabase local ne garantit jamais totalement.
- micromamba résout le problème ecCodes sur les trois systèmes, pas seulement
  Windows.

**Défavorables, à accepter explicitement**

- **Le développement de la base exige une connexion internet.** Il n'y a plus de
  base locale hors ligne.
- **Le projet Supabase de développement est partagé** : une migration
  destructrice y est visible par toute l'équipe immédiatement. La discipline
  expand/contract du §25.3 devient obligatoire dès le développement, pas
  seulement en production.
- **La parité d'environnement n'est plus garantie par l'image.** Elle repose sur
  `environment.yml` et son fichier de verrouillage, qu'il faut régénérer et
  committer à chaque modification de dépendance.
- Le déploiement du worker devient un script de configuration système à écrire
  et à maintenir, là où une image était reproductible par construction.

## Alternatives écartées

- **PostgreSQL + PostGIS natif Windows** : permet le travail hors ligne, mais
  laisse Auth, Storage et RLS non testés localement. Retenu comme complément
  possible, pas comme socle.
- **WSL2** : ne résout rien, puisque le CLI Supabase y réclame également Docker.
- **pip + `ecmwflibs`** : fournit ecCodes sur Windows, mais avec une couverture
  de versions plus étroite et une maintenance moins prévisible que conda-forge.
