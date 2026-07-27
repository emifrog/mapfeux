-- =============================================================================
-- 20260727120100 — Vocabulaires contrôlés
--
-- Cahier §17.4 et annexe D. Ces types doivent rester alignés sur
-- packages/domain/src/vocabulary.ts : toute divergence est un défaut bloquant.
--
-- Les trois dimensions de statut sont trois types distincts. Leur fusion en un
-- unique champ « statut » est explicitement interdite par le cahier §2.4.
-- =============================================================================

-- Nature de l'information exposée --------------------------------------------
create type app.provenance as enum (
  'observation',
  'algorithmic_inference',
  'model_estimate',
  'official_information',
  'editorial_correction',
  'external_report'
);

comment on type app.provenance is
  'Provenance obligatoire de toute information publiée (cahier §2.4).';

-- Fiabilité publique, sans jugement de gravité ni de surface -------------------
create type app.confidence_level as enum ('low', 'medium', 'high');

-- Dimension 1 : fraîcheur technique de l'événement ----------------------------
create type fire.freshness_status as enum (
  'new',
  'recent',
  'not_recent',
  'archived',
  'hidden'
);

comment on type fire.freshness_status is
  'Ancienneté de la dernière observation. Ne conclut jamais à une extinction.';

-- Dimension 2 : niveau de vérification de l'existence -------------------------
create type fire.verification_status as enum (
  'satellite_detection',
  'probable_event',
  'publicly_reported',
  'officially_confirmed'
);

-- Dimension 3 : statut opérationnel officiel, toujours nullable ---------------
create type fire.official_control_status as enum (
  'active',
  'contained',
  'controlled',
  'extinguished'
);

comment on type fire.official_control_status is
  'Renseigné uniquement à partir d''une publication d''autorité, avec source et date.';

create type fire.timeline_entry_type as enum (
  'detection',
  'grouping',
  'smoke_forecast',
  'wind_change',
  'official_update',
  'editorial_correction',
  'status_change'
);

create type fire.timeline_visibility as enum ('public', 'internal', 'suppressed');

create type fire.attachment_method as enum ('auto', 'manual');

-- Territoires ------------------------------------------------------------------
create type app.territory_type as enum (
  'country',
  'region',
  'department',
  'collectivity',
  'custom'
);

create type app.territory_status as enum ('draft', 'pilot', 'active', 'disabled');

-- Ingestion --------------------------------------------------------------------
create type ingest.source_status as enum ('active', 'paused', 'degraded', 'disabled');

create type ingest.run_status as enum (
  'running',
  'success',
  'partial',
  'failed',
  'skipped'
);

-- Administration et audit -------------------------------------------------------
create type admin.role as enum (
  'viewer_admin',
  'content_admin',
  'data_admin',
  'super_admin'
);

create type admin.profile_status as enum ('invited', 'active', 'suspended');

create type audit.actor_type as enum ('job', 'admin', 'system');
