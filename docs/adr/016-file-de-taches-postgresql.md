# ADR-016 — File de tâches PostgreSQL au lieu de Celery et Redis

- **Statut** : accepté, réversible
- **Date** : 2026-07-27
- **Amende** : cahier §10.2 (Redis, Celery) et §16.8 (Celery Beat)

## Contexte

Le cahier prévoit Celery avec Redis pour la file de tâches, le verrouillage
distribué et l'anti-duplication. [ADR-014](014-environnement-sans-docker.md)
retire Docker de la chaîne, or Redis n'a pas de build natif Windows officiel.

Par ailleurs, le §26.1 retient l'hypothèse d'un développement principalement
solo sur 30 à 42 semaines. Chaque composant d'infrastructure supplémentaire est
un service à installer, superviser, sauvegarder et redémarrer.

## Décision

Le MVP n'utilise ni Redis ni Celery. À la place :

- **File de tâches** : une table PostgreSQL consommée avec
  `SELECT ... FOR UPDATE SKIP LOCKED`, motif éprouvé et transactionnel.
- **Verrou distribué** : `pg_advisory_lock`, qui couvre exactement le besoin du
  §16.1 étape 1. L'index partiel `import_runs_single_running` en est le second
  garde-fou.
- **Planification** : APScheduler dans le processus worker, avec le calendrier
  du §16.8. Les tâches d'entretien légères restent sur `pg_cron`.

L'atout décisif est transactionnel : l'insertion d'une tâche et l'écriture des
données qui la motivent partagent la même transaction. Avec Redis, un `commit`
réussi suivi d'un `enqueue` échoué produit une tâche perdue silencieusement.

## Conséquences

**Favorables**

- Deux composants d'infrastructure en moins, et rien à installer sous Windows.
- La file est sauvegardée et restaurée avec la base, sans procédure séparée.
- L'état des tâches est inspectable en SQL, y compris depuis l'administration.

**Défavorables**

- Le débit est très inférieur à celui de Redis. Acceptable ici : les volumes du
  §6.3 se comptent en dizaines de milliers de détections par jour, pas en
  messages par seconde.
- Le scrutin de la file génère une charge de fond sur la base, à surveiller.
- APScheduler dans le processus worker suppose **une seule instance de
  planificateur**. Une montée horizontale du worker (§6.3) imposera d'élire un
  planificateur, ou de revenir à un ordonnanceur externe.

## Condition de réexamen

Cette décision est explicitement réversible. Elle est réexaminée si l'un de ces
seuils est franchi :

- plus d'une instance de worker nécessaire en régime permanent ;
- durée d'attente en file supérieure à une minute en pointe ;
- recalcul simultané de plus d'une centaine de panaches devenu courant (§24.6).

Les interfaces `pipelines/` sont écrites pour que le passage à Celery ne touche
que la couche d'ordonnancement, jamais le contenu des tâches.
