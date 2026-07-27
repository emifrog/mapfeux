-- =============================================================================
-- 20260727120000 — Schémas, extensions et conventions communes
--
-- Cahier §12.1 et §12.2.
--
-- Principe : aucun schéma interne n'est exposé par la Data API. Seul `api`
-- reçoit les grants de lecture pour `anon` et `authenticated`. Les tables
-- brutes restent inaccessibles à ces rôles, y compris en cas d'erreur de RLS.
-- =============================================================================

create extension if not exists postgis with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists pg_stat_statements with schema extensions;

-- Schémas internes ------------------------------------------------------------
create schema if not exists app;      -- territoires, contenus, configurations
create schema if not exists geo;      -- géométries administratives
create schema if not exists fire;     -- détections et événements
create schema if not exists meteo;    -- runs météo, vents, panaches
create schema if not exists air;      -- qualité de l'air
create schema if not exists radar;    -- métadonnées radar
create schema if not exists ingest;   -- imports, fichiers, erreurs
create schema if not exists admin;    -- profils et habilitations
create schema if not exists audit;    -- journaux immuables

-- Schéma public exposé --------------------------------------------------------
create schema if not exists api;      -- vues et fonctions publiques stables

comment on schema api is
  'Surface publique stable. Seul schéma exposé par la Data API (cahier §12.1).';

-- Verrouillage par défaut -----------------------------------------------------
-- Aucun droit implicite sur les schémas internes, pour les rôles clients.
revoke all on schema app, geo, fire, meteo, air, radar, ingest, admin, audit
  from anon, authenticated;

revoke all on schema public from anon, authenticated;
grant usage on schema public to anon, authenticated;

-- Les objets créés plus tard ne doivent pas hériter de droits par défaut.
alter default privileges in schema app, geo, fire, meteo, air, radar, ingest, admin, audit
  revoke all on tables from anon, authenticated;
alter default privileges in schema app, geo, fire, meteo, air, radar, ingest, admin, audit
  revoke all on functions from anon, authenticated;
alter default privileges in schema app, geo, fire, meteo, air, radar, ingest, admin, audit
  revoke all on sequences from anon, authenticated;

grant usage on schema api to anon, authenticated;

-- Fonctions utilitaires -------------------------------------------------------

-- Horodatage de modification, appliqué par trigger sur les tables mutables.
create or replace function app.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function app.set_updated_at is
  'Trigger BEFORE UPDATE : maintient updated_at sans dépendre de l''appelant.';
