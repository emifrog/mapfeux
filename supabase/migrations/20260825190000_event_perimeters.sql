-- =============================================================================
-- 20260825190000 — Périmètres versionnés des événements (jalon J9)
--
-- Cahier v2.1 §13.23 et FR-090 à FR-096. Un événement peut porter zéro, un ou
-- plusieurs périmètres, de natures différentes — officiel, institutionnel,
-- EFFIS/Copernicus, estimé, éditorial, historique — et chaque version
-- **s'ajoute** au lieu de remplacer : `supersedes_id` chaîne les versions, la
-- relecture les rejouera (FR-094), et un périmètre erroné se masque
-- (`is_public`) sans détruire ni la géométrie ni le fichier source (FR-096).
--
-- La surface est **recalculée** chez nous, sur l'ellipsoïde, et la méthode
-- consignée (FR-095) ; la surface annoncée par la source est conservée à
-- côté, jamais confondue. La confiance a sa propre échelle : un périmètre
-- officiel n'est pas « confiance élevée », il est hors de cette échelle —
-- d'où `not_applicable`, absent d'`app.confidence_level` et propre à cet
-- usage.
--
-- EFFIS entre au registre des sources, `disabled` comme CAMS et le radar
-- avant lui : déclaré pour que le registre reflète le cahier, arrêté pour
-- que /statut le dise sans annoncer une panne.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

do $$
begin
  create type fire.perimeter_type as enum
    ('official', 'institutional', 'effis', 'estimated', 'editorial', 'historical');
exception
  when duplicate_object then null;
end
$$;

comment on type fire.perimeter_type is
  'Nature d''un périmètre (FR-092). Un type satellitaire ou estimé n''est jamais présenté comme un contour opérationnel (FR-093).';

do $$
begin
  create type fire.perimeter_confidence as enum
    ('low', 'medium', 'high', 'not_applicable');
exception
  when duplicate_object then null;
end
$$;

comment on type fire.perimeter_confidence is
  'Confiance d''un périmètre (§13.23). not_applicable : la source fait autorité, l''échelle ne s''applique pas.';

create table if not exists fire.event_perimeters (
  id uuid primary key default gen_random_uuid(),

  event_id uuid not null references fire.events (id) on delete cascade,
  source_id uuid not null references ingest.data_sources (id),

  perimeter_type fire.perimeter_type not null,

  -- L'instant que la géométrie représente — pas celui où on l'a apprise.
  valid_at timestamptz not null,
  published_at timestamptz,
  imported_at timestamptz not null default now(),

  geometry extensions.geometry(MultiPolygon, 4326) not null,

  -- Surface recalculée chez nous (FR-095) ; celle annoncée par la source
  -- reste à côté. Les confondre ferait dire à MapFeux ce qu'il n'a pas
  -- mesuré.
  area_ha numeric(10, 2) not null check (area_ha >= 0),
  source_area_ha numeric(10, 2),
  resolution_m numeric(8, 1),

  confidence_level fire.perimeter_confidence not null,
  method text not null,

  is_public boolean not null default true,

  supersedes_id uuid references fire.event_perimeters (id),

  raw_payload jsonb not null default '{}'::jsonb,

  constraint event_perimeters_geometry_valid
    check (extensions.st_isvalid(geometry)),
  constraint event_perimeters_geometry_not_empty
    check (not extensions.st_isempty(geometry))
);

comment on table fire.event_perimeters is
  'Périmètres versionnés, multi-sources (§13.23). Les versions s''ajoutent, le masquage ne détruit rien (FR-096).';

create index if not exists event_perimeters_geometry_gist
  on fire.event_perimeters using gist (geometry);

create index if not exists event_perimeters_event_valid_idx
  on fire.event_perimeters (event_id, valid_at desc);

alter table fire.event_perimeters enable row level security;

-- =============================================================================
-- EFFIS au registre des sources
-- =============================================================================

insert into ingest.data_sources
  (key, name, provider, status, expected_interval, stale_after, documentation_url,
   license_name, attribution, retention_policy, settings)
values
  (
    'effis',
    'EFFIS — surfaces brûlées Copernicus',
    'Copernicus EMS / JRC',
    'disabled',
    interval '24 hours',
    interval '72 hours',
    'https://forest-fire.emergency.copernicus.eu/',
    'Copernicus Licence',
    'European Forest Fire Information System (EFFIS) — Copernicus Emergency Management Service',
    'GeoJSON bruts 30 jours ; périmètres conservés sans limite',
    '{}'::jsonb
  )
on conflict (key) do nothing;

-- =============================================================================
-- Droits de l'ingestion automatisée — la synchronisation EFFIS viendra
-- =============================================================================

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant select, insert on fire.event_perimeters to mapfeux_ingest;
  end if;
end
$$;
