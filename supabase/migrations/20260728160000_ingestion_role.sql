-- =============================================================================
-- 20260728160000 — Rôle dédié à l'ingestion automatisée
--
-- Cahier §25.2 et annexe C.
--
-- L'ordonnanceur tourne hors de la machine de développement, donc sa chaîne de
-- connexion vit chez un tiers — aujourd'hui les secrets GitHub Actions. Y
-- placer `postgres` reviendrait à confier la base entière à ce tiers : un
-- secret qui fuite donnerait la lecture des profils d'administration, du
-- journal d'audit, et le droit de tout effacer.
--
-- Ce rôle ne peut faire que ce que fait `scripts/run-ingestion.py` : lire le
-- registre des sources, ouvrir des exécutions d'import, insérer des détections,
-- construire des événements et reconstruire les instantanés publics. Il ne peut
-- lire ni `admin`, ni `audit`, ni les messages officiels ; il ne peut effacer
-- aucune ligne, ni modifier le schéma.
--
-- ## Mot de passe
--
-- Volontairement absent d'ici. Une migration est versionnée : un mot de passe
-- écrit dans ce fichier serait publié avec le dépôt. Tant qu'aucun mot de passe
-- n'est posé, le rôle ne peut pas s'authentifier — l'état par défaut est donc
-- le plus sûr.
--
-- À exécuter une fois dans l'éditeur SQL du tableau de bord, avec une valeur
-- engendrée aléatoirement et jamais réutilisée :
--
--     alter role mapfeux_ingest password 'valeur-longue-et-aleatoire';
--
-- ## BYPASSRLS
--
-- Les tables internes ont RLS activé sans aucune politique : hors du
-- propriétaire, elles sont invisibles et non modifiables. Sans cet attribut, le
-- rôle verrait zéro ligne partout et chaque insertion serait refusée.
--
-- L'attribut ne donne **aucun** droit sur une table : il lève seulement le
-- filtrage par ligne là où un droit existe déjà. Ce qui n'est pas accordé
-- ci-dessous reste inaccessible.
-- =============================================================================

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    create role mapfeux_ingest login;
  end if;
end
$$;

-- Appliqué inconditionnellement : rejouer la migration doit corriger un rôle
-- créé à la main sans l'attribut. Le mot de passe n'est pas touché.
alter role mapfeux_ingest bypassrls;

-- Le nom de la base varie entre le projet hébergé et les bases de vérification.
do $$
begin
  execute format('grant connect on database %I to mapfeux_ingest', current_database());
end
$$;

grant usage on schema fire, ingest, geo, extensions to mapfeux_ingest;

-- Registre des sources : lecture seule. Le worker s'y rattache, il ne le décrit
-- pas.
grant select on ingest.data_sources to mapfeux_ingest;

-- Cycle de vie d'un import : ouverture, puis clôture avec ses compteurs (§16.1).
grant select, insert, update on ingest.import_runs to mapfeux_ingest;

-- Observations. La mise à jour sert au seul rattachement à une source thermique
-- connue, qui classe la détection sans jamais la supprimer (FR-036).
grant select, insert, update on fire.detections to mapfeux_ingest;
grant select on fire.known_thermal_sources to mapfeux_ingest;

-- Inférences. Aucun droit d'effacement : défaire un regroupement est une
-- opération de calibration, qui se fait depuis un poste de développement avec
-- les droits correspondants, pas depuis une tâche planifiée.
grant select, insert, update on fire.events to mapfeux_ingest;
grant select, insert on fire.event_detections to mapfeux_ingest;
grant select, insert on fire.event_timeline_entries to mapfeux_ingest;

-- Rattachement d'un événement à sa commune la plus proche.
grant select on geo.municipalities to mapfeux_ingest;

grant execute on function fire.generate_public_id(text) to mapfeux_ingest;
grant execute on function fire.ensure_detection_partition(date) to mapfeux_ingest;
grant execute on function fire.recompute_event_aggregates(uuid) to mapfeux_ingest;
grant execute on function fire.refresh_event_snapshot(uuid) to mapfeux_ingest;

comment on role mapfeux_ingest is
  'Ingestion automatisée uniquement. Aucun accès à admin, audit ou aux messages officiels ; aucun droit d''effacement.';
