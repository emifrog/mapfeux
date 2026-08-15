-- =============================================================================
-- 20260810150000 — Tables météo du panache (jalon J8)
--
-- Cahier v2.1 §13.12 à §13.16 : `model_runs`, `wind_samples`,
-- `smoke_forecasts`, `smoke_steps`, `affected_municipalities`. Le schéma
-- `meteo` porte déjà la vigilance ; il reçoit ici les structures du calcul.
--
-- Aucune de ces tables n'est exposée par la Data API : le panache ne devient
-- public qu'avec sa formulation validée (§22.5) et sa fonction `api.*` dédiée,
-- qui viendront avec le calcul. Créer les tables d'abord n'affiche rien.
--
-- Idempotente de bout en bout (dette « migrations hors bande », plan §15) :
-- elle peut être appliquée par script sur la base vivante puis rejouée par
-- `db push` sans erreur.
-- =============================================================================

-- État d'import d'un run : ce que NOUS détenons localement, pas l'état du run
-- chez le fournisseur. `partial` est l'état nominal de l'archivage FWI — une
-- échéance par jour sur les quarante-huit du run — et le restera tant que
-- l'ingestion du panache n'aura pas élargi la fenêtre.
do $$
begin
  create type meteo.model_run_import_status as enum
    ('pending', 'partial', 'complete', 'failed');
exception
  when duplicate_object then null;
end
$$;

comment on type meteo.model_run_import_status is
  'Couverture locale du run : partial = une partie des échéances archivée.';

-- =============================================================================
-- §13.12 — Registre des runs de modèle
-- =============================================================================

create table if not exists meteo.model_runs (
  id uuid primary key default gen_random_uuid(),

  provider text not null,
  model text not null,
  run_at timestamptz not null,

  -- Domaine et géométrie de grille, constants pour un produit donné mais
  -- consignés par run : un changement de résolution chez le fournisseur doit
  -- être un fait daté, pas une surprise silencieuse.
  domain text not null,
  resolution text not null,
  projection text not null default 'EPSG:4326',

  -- Échéances (en heures depuis le run) effectivement disponibles dans notre
  -- stockage — l'union de ce que les imports successifs ont déposé.
  available_leads integer[] not null default '{}',

  import_status meteo.model_run_import_status not null default 'pending',

  -- Dernier extrait déposé. L'inventaire complet vit dans
  -- `metadata->'files'` : un même run peut être couvert par plusieurs
  -- tranches d'échéances, chacune son fichier et son empreinte.
  source_path text,
  checksum text,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint model_runs_run_unique unique (provider, model, run_at)
);

-- Le v2.1 ajoute au §13.12 un indicateur d'archivage froid des extraits FWI
-- (PR-1). En `add column if not exists` : la table peut préexister chez qui a
-- rejoué la migration avant cet ajout.
alter table meteo.model_runs
  add column if not exists fwi_archived boolean not null default false;

comment on table meteo.model_runs is
  'Runs de modèle météo dont des champs sont détenus localement. Cahier v2.1 §13.12.';
comment on column meteo.model_runs.fwi_archived is
  'Les extraits FWI de ce run sont déposés en stockage froid (PR-1). Cahier v2.1 §13.12.';
comment on column meteo.model_runs.available_leads is
  'Échéances (heures depuis le run) présentes dans le stockage froid — union des imports.';
comment on column meteo.model_runs.source_path is
  'Dernier extrait déposé (compartiment/chemin). Inventaire complet dans metadata.files.';

create index if not exists model_runs_model_run_at_idx
  on meteo.model_runs (model, run_at desc);

drop trigger if exists model_runs_set_updated_at on meteo.model_runs;
create trigger model_runs_set_updated_at
  before update on meteo.model_runs
  for each row execute function app.set_updated_at();

alter table meteo.model_runs enable row level security;

-- =============================================================================
-- §13.13 — Échantillons de vent aux points utilisés par les événements
-- =============================================================================

create table if not exists meteo.wind_samples (
  id uuid primary key default gen_random_uuid(),

  model_run_id uuid not null
    references meteo.model_runs (id) on delete cascade,

  location extensions.geometry(Point, 4326) not null,
  -- « 10m » pour le vent de surface AROME. Textuel : un niveau modèle n'est
  -- pas toujours une altitude en mètres.
  level text not null default '10m',
  valid_at timestamptz not null,

  u_ms numeric(6, 2) not null,
  v_ms numeric(6, 2) not null,
  speed_ms numeric(6, 2) not null check (speed_ms >= 0),
  -- Direction météorologique : d'où vient le vent, en degrés depuis le nord.
  direction_deg numeric(5, 1) not null
    check (direction_deg >= 0 and direction_deg < 360),

  interpolation text not null,
  -- Distance du point à la cellule de grille la plus proche portant une
  -- valeur : au-delà d'un seuil, l'échantillon dégrade la confiance (§18.4).
  cell_distance_m numeric(8, 1),

  created_at timestamptz not null default now()
);

comment on table meteo.wind_samples is
  'Vent interpolé aux points des événements. La grille complète reste dans le stockage objet (§13.13).';

create index if not exists wind_samples_run_valid_idx
  on meteo.wind_samples (model_run_id, valid_at);

alter table meteo.wind_samples enable row level security;

-- =============================================================================
-- §13.14 — Prévisions de panache
-- =============================================================================

create table if not exists meteo.smoke_forecasts (
  id uuid primary key default gen_random_uuid(),

  event_id uuid not null references fire.events (id) on delete cascade,
  -- `restrict` : une prévision sans son run perdrait sa provenance, et le
  -- versionnement §18.6 l'interdit. Supprimer un run exige d'avoir d'abord
  -- retiré les prévisions qui s'y adossent.
  model_run_id uuid not null
    references meteo.model_runs (id) on delete restrict,

  algorithm_version text not null,
  generated_at timestamptz not null default now(),
  valid_from timestamptz not null,
  valid_to timestamptz not null,

  geometry extensions.geometry(MultiPolygon, 4326) not null,
  centerline extensions.geometry(LineString, 4326),

  confidence_level app.confidence_level not null,

  -- Paramètres reproductibles : coefficients, horizon, pas, garde-fous,
  -- commit du worker, checksum des entrées (§18.6). En jsonb : c'est un
  -- dossier de calcul, pas une surface de requête.
  parameters jsonb not null,
  quality_flags text[] not null default '{}',

  is_current boolean not null default false,

  constraint smoke_forecasts_validity check (valid_to > valid_from),
  -- §18.5 : géométrie valide obligatoire, en contrainte et non en discipline.
  constraint smoke_forecasts_geometry_valid
    check (extensions.st_isvalid(geometry)),
  constraint smoke_forecasts_centerline_valid
    check (centerline is null or extensions.st_isvalid(centerline))
);

comment on table meteo.smoke_forecasts is
  'Panache indicatif par événement (§13.14, §18). Jamais présenté comme une mesure.';

-- Une seule prévision publiée par événement : `is_current` est une bascule,
-- pas un historique — l'historique, ce sont les autres lignes.
create unique index if not exists smoke_forecasts_current_unique
  on meteo.smoke_forecasts (event_id)
  where is_current;

create index if not exists smoke_forecasts_event_idx
  on meteo.smoke_forecasts (event_id, generated_at desc);

alter table meteo.smoke_forecasts enable row level security;

-- =============================================================================
-- §13.15 — Pas temporels du panache
-- =============================================================================

create table if not exists meteo.smoke_steps (
  forecast_id uuid not null
    references meteo.smoke_forecasts (id) on delete cascade,
  step_index smallint not null check (step_index >= 0),

  valid_at timestamptz not null,
  center extensions.geometry(Point, 4326) not null,
  footprint extensions.geometry(Polygon, 4326) not null,

  speed_ms numeric(6, 2) not null check (speed_ms >= 0),
  direction_deg numeric(5, 1) not null
    check (direction_deg >= 0 and direction_deg < 360),
  width_m numeric(8, 1) not null check (width_m >= 0),
  -- Distance cumulée depuis le point d'origine — c'est elle que borne le
  -- garde-fou de distance maximale par horizon (§18.5).
  distance_m numeric(9, 1) not null check (distance_m >= 0),

  quality_flags text[] not null default '{}',

  primary key (forecast_id, step_index),
  constraint smoke_steps_valid_at_unique unique (forecast_id, valid_at),
  constraint smoke_steps_footprint_valid
    check (extensions.st_isvalid(footprint))
);

comment on table meteo.smoke_steps is
  'Un pas temporel du panache par ligne (§13.15). La relecture (FR-094) lira ici.';

alter table meteo.smoke_steps enable row level security;

-- =============================================================================
-- §13.16 — Communes potentiellement concernées
-- =============================================================================

create table if not exists meteo.affected_municipalities (
  forecast_id uuid not null
    references meteo.smoke_forecasts (id) on delete cascade,
  -- Le référentiel communal date une commune disparue au lieu de la supprimer
  -- (§13.2) : la référence ne casse donc jamais rétroactivement.
  insee_code text not null references geo.municipalities (insee_code),

  first_intersection_at timestamptz,
  last_intersection_at timestamptz,

  overlap_area_km2 numeric(8, 2) not null check (overlap_area_km2 >= 0),
  overlap_ratio numeric(5, 4) not null
    check (overlap_ratio >= 0 and overlap_ratio <= 1),
  -- Rang d'exposition indicatif, pour le tri FR-072 : heure d'arrivée
  -- estimée puis niveau d'exposition. Jamais présenté comme une mesure.
  exposure_rank smallint not null check (exposure_rank > 0),
  confidence_level app.confidence_level not null,

  primary key (forecast_id, insee_code),
  constraint affected_municipalities_window
    check (
      first_intersection_at is null
      or last_intersection_at is null
      or last_intersection_at >= first_intersection_at
    )
);

comment on table meteo.affected_municipalities is
  'Communes « potentiellement concernées » par un panache (§13.16, FR-110 à FR-114). Le libellé public est obligatoire.';

alter table meteo.affected_municipalities enable row level security;

-- =============================================================================
-- Droits de l'ingestion automatisée
--
-- Seul le registre des runs est ouvert à `mapfeux_ingest` : c'est ce que
-- l'archivage quotidien renseigne dès aujourd'hui. Les tables de calcul
-- recevront leurs droits avec le pipeline qui les écrit — un droit sans
-- écrivain est une surface d'attaque sans bénéfice.
-- =============================================================================

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant usage on schema meteo to mapfeux_ingest;
    grant select, insert, update on meteo.model_runs to mapfeux_ingest;
  end if;
end
$$;
