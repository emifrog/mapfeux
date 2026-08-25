-- =============================================================================
-- 20260825170000 — Tables des schémas air et radar (jalon J9)
--
-- Cahier v2.1 §13.17 et §13.18 ; §16.5, §16.6, §19. Les deux schémas
-- existaient depuis l'origine, vides et déclarés au registre des sources en
-- « à venir » : voici leurs structures. Rien de public n'y est branché — les
-- couches d'affichage viendront avec leurs connecteurs, et la panne de l'un
-- ne devra jamais toucher la carte (FR-125), ce que la séparation des
-- schémas prépare par construction.
--
-- `air.model_runs` reprend le vocabulaire d'état de `meteo.model_runs` — un
-- seul enum pour dire « ce que nous détenons localement d'un run », plutôt
-- qu'un synonyme par schéma. La publication est **atomique par run** :
-- `is_current` bascule d'un run à l'autre dans une transaction, l'ancien et
-- ses fichiers restent (§16.5, « conservation de la version précédente »).
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

-- =============================================================================
-- §13.17 — Runs CAMS détenus
-- =============================================================================

create table if not exists air.model_runs (
  id uuid primary key default gen_random_uuid(),

  provider text not null,
  model text not null,
  run_at timestamptz not null,

  domain text not null,
  resolution text not null,
  projection text not null default 'EPSG:4326',

  -- Échéances (heures depuis le run) effectivement détenues.
  available_leads integer[] not null default '{}',

  import_status meteo.model_run_import_status not null default 'pending',

  -- Le run publié — celui que l'affichage et l'échantillonnage servent.
  -- La bascule est atomique ; le run précédent et ses fichiers survivent.
  is_current boolean not null default false,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint air_model_runs_run_unique unique (provider, model, run_at)
);

comment on table air.model_runs is
  'Runs CAMS dont des champs sont détenus localement. Cahier §13.17 ; publication atomique par bascule d''is_current (§16.5).';

create unique index if not exists air_model_runs_current_key
  on air.model_runs (model)
  where is_current;

drop trigger if exists air_model_runs_set_updated_at on air.model_runs;
create trigger air_model_runs_set_updated_at
  before update on air.model_runs
  for each row execute function app.set_updated_at();

alter table air.model_runs enable row level security;

-- =============================================================================
-- §13.17 — Fichiers produits par run : bruts, COG, tuiles
-- =============================================================================

create table if not exists air.grid_assets (
  id uuid primary key default gen_random_uuid(),

  model_run_id uuid not null
    references air.model_runs (id) on delete cascade,

  -- `pm2_5`, `pm10` au minimum (FR-120) ; une AASQA future passera par un
  -- adaptateur et une attribution distincte (FR-122), jamais par une valeur
  -- glissée ici sous un nom voisin.
  pollutant text not null
    check (pollutant ~ '^[a-z0-9_]+$'),
  unit text not null,

  lead_hours integer not null check (lead_hours >= 0),
  valid_at timestamptz not null,

  -- Ce que le fichier est : le brut importé, le COG d'archive et de calcul,
  -- ou la tuile servie au navigateur (§19.1). Le JSON brut vers le client
  -- est interdit par construction : il n'a pas de forme ici.
  kind text not null check (kind in ('raw', 'cog', 'tile')),

  extent text not null,
  resolution text not null,

  asset_path text not null,
  checksum text not null,

  -- Palette et légende versionnées, méthode de conversion (§19.1).
  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),

  constraint grid_assets_unique unique (model_run_id, pollutant, kind, lead_hours)
);

comment on table air.grid_assets is
  'Fichiers d''un run CAMS : brut, COG ou tuile, par polluant et échéance. Cahier §13.17 et §19.1.';

create index if not exists grid_assets_lookup_idx
  on air.grid_assets (pollutant, kind, valid_at desc);

alter table air.grid_assets enable row level security;

-- =============================================================================
-- §13.18 — Frames radar
-- =============================================================================

do $$
begin
  create type radar.frame_status as enum ('pending', 'ready', 'failed', 'expired');
exception
  when duplicate_object then null;
end
$$;

comment on type radar.frame_status is
  'État d''une frame : importée, servable, échouée, ou expirée (§16.6).';

create table if not exists radar.frames (
  id uuid primary key default gen_random_uuid(),

  product text not null,
  acquired_at timestamptz not null,
  imported_at timestamptz not null default now(),

  projection text not null,
  extent text not null,

  raw_path text,
  web_path text,

  status radar.frame_status not null default 'pending',
  checksum text,

  -- L'expiration est une donnée, pas un jugement : une frame radar de plus
  -- d'une heure ne décrit plus rien, et l'animation ne doit jamais la servir
  -- (§16.6, FR-123).
  expires_at timestamptz not null,

  constraint radar_frames_unique unique (product, acquired_at)
);

comment on table radar.frames is
  'Frames de la mosaïque radar : brut, image web, état, expiration. Cahier §13.18.';

create index if not exists radar_frames_timeline_idx
  on radar.frames (product, acquired_at desc)
  where status = 'ready';

alter table radar.frames enable row level security;

-- =============================================================================
-- Droits de l'ingestion automatisée
-- =============================================================================

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant usage on schema air to mapfeux_ingest;
    grant usage on schema radar to mapfeux_ingest;
    grant select, insert, update on air.model_runs to mapfeux_ingest;
    grant select, insert, update on air.grid_assets to mapfeux_ingest;
    grant select, insert, update on radar.frames to mapfeux_ingest;
  end if;
end
$$;
