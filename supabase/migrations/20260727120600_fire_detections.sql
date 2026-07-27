-- =============================================================================
-- 20260727120600 — Détections thermiques satellitaires
--
-- Cahier §13.5, §5.4 et §12.4.
--
-- Décision de conception : la table est créée partitionnée par `acquired_at`
-- dès l'origine, même à faible volumétrie. PostgreSQL impose que la clé de
-- partitionnement figure dans toute contrainte d'unicité ; convertir plus tard
-- une table non partitionnée obligerait à réécrire la clé primaire et la clé
-- d'idempotence sur plusieurs millions de lignes. Le cahier §12.4 prévoyait le
-- partitionnement « lorsque la volumétrie le justifie » et §13.5 déclarait des
-- clés simples : les deux étaient incompatibles. Voir ADR-015.
--
-- `provider_key` est un hash stable de (fournisseur, produit, satellite,
-- capteur, acquired_at, latitude, longitude, version). Comme il encode déjà
-- l'heure d'acquisition, l'unicité sur (provider_key, acquired_at) est
-- sémantiquement équivalente à l'unicité sur provider_key seul. FR-033.
-- =============================================================================

create table fire.known_thermal_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text not null,
  location extensions.geometry(Point, 4326) not null,
  -- Rayon de correspondance en mètres autour du site connu.
  match_radius_m integer not null default 1000,
  notes text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),

  constraint known_thermal_sources_category check (
    category in ('industrial', 'flare', 'volcano', 'power_plant', 'agricultural', 'other')
  ),
  constraint known_thermal_sources_radius check (match_radius_m between 100 and 20000)
);

comment on table fire.known_thermal_sources is
  'Sites thermiques récurrents. Une correspondance classe la détection sans jamais l''effacer. §13.11.';

create index known_thermal_sources_location_gix
  on fire.known_thermal_sources using gist (location)
  where is_active;

alter table fire.known_thermal_sources enable row level security;

-- =============================================================================
-- Détections
-- =============================================================================

create table fire.detections (
  id uuid not null default gen_random_uuid(),
  provider_key text not null,
  source_id uuid not null references ingest.data_sources (id) on delete restrict,
  import_run_id uuid references ingest.import_runs (id) on delete set null,
  sensor text not null,
  satellite text not null,
  product_version text,
  -- Heure d'observation satellitaire en UTC. FR-032.
  acquired_at timestamptz not null,
  imported_at timestamptz not null default now(),
  location extensions.geometry(Point, 4326) not null,
  latitude double precision not null,
  longitude double precision not null,
  confidence_raw text,
  confidence_score numeric(4, 3),
  frp_mw numeric(10, 3),
  brightness numeric(8, 3),
  day_night char(1),
  scan_km numeric(6, 3),
  track_km numeric(6, 3),
  thermal_type text,
  -- Donnée fournisseur conservée telle quelle. Jamais modifiée, jamais exposée
  -- publiquement. ADR-004 et §14.2.
  raw_payload jsonb not null,
  known_source_id uuid references fire.known_thermal_sources (id) on delete set null,
  is_public boolean not null default true,

  primary key (id, acquired_at),
  constraint detections_provider_key_unique unique (provider_key, acquired_at),
  constraint detections_confidence_range
    check (confidence_score is null or confidence_score between 0 and 1),
  constraint detections_frp_positive check (frp_mw is null or frp_mw >= 0),
  constraint detections_day_night check (day_night is null or day_night in ('D', 'N')),
  constraint detections_latitude_range check (latitude between -90 and 90),
  constraint detections_longitude_range check (longitude between -180 and 180)
) partition by range (acquired_at);

comment on table fire.detections is
  'Détections FIRMS brutes et immuables. Partitionnée par mois d''acquisition (§12.4).';
comment on column fire.detections.location is
  'Centre approximatif du pixel satellite, pas la position du foyer. FR-035.';

create index detections_acquired_at_idx on fire.detections (acquired_at desc);
create index detections_location_gix on fire.detections using gist (location);
create index detections_public_recent_idx
  on fire.detections (acquired_at desc)
  where is_public;
create index detections_known_source_idx
  on fire.detections (known_source_id)
  where known_source_id is not null;

alter table fire.detections enable row level security;

-- Une observation datée dans le futur trahit une erreur de fuseau côté
-- connecteur. Le contrôle passe par un trigger : une contrainte CHECK ne peut
-- pas appeler now(), qui n'est pas immuable. §24.4
create or replace function fire.reject_future_acquisition()
returns trigger
language plpgsql
as $$
begin
  if new.acquired_at > now() + interval '1 hour' then
    raise exception 'Détection datée dans le futur : % (import %)', new.acquired_at, new.import_run_id
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

create trigger detections_reject_future_acquisition
  before insert or update of acquired_at on fire.detections
  for each row execute function fire.reject_future_acquisition();

-- =============================================================================
-- Gestion des partitions
-- =============================================================================

create or replace function fire.ensure_detection_partition(target date)
returns text
language plpgsql
security definer
set search_path = fire, pg_temp
as $$
declare
  start_ts timestamptz := (date_trunc('month', target::timestamp) at time zone 'UTC');
  end_ts timestamptz :=
    ((date_trunc('month', target::timestamp) + interval '1 month') at time zone 'UTC');
  part_name text := 'detections_' || to_char(start_ts at time zone 'UTC', 'YYYY_MM');
begin
  if to_regclass('fire.' || quote_ident(part_name)) is null then
    execute format(
      'create table fire.%I partition of fire.detections for values from (%L) to (%L)',
      part_name, start_ts, end_ts
    );
    execute format('alter table fire.%I enable row level security', part_name);
  end if;

  return part_name;
end;
$$;

comment on function fire.ensure_detection_partition is
  'Crée si nécessaire la partition mensuelle couvrant la date fournie. Idempotente.';

-- Partition par défaut : aucune détection ne doit être perdue si une partition
-- mensuelle manque. Les partitions nominales sont créées à l'avance par tâche
-- planifiée afin que celle-ci reste vide.
create table fire.detections_default partition of fire.detections default;
alter table fire.detections_default enable row level security;

-- Amorce : mois courant et trois mois suivants.
select fire.ensure_detection_partition((date_trunc('month', now()) + (n || ' months')::interval)::date)
from generate_series(0, 3) as n;
