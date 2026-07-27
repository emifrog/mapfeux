-- =============================================================================
-- 20260727120300 — Territoires et communes
--
-- Cahier §13.1, §13.2 et §2.4 « multi-territoires natif ».
--
-- Aucune logique métier ne doit contenir de condition sur le département 06 :
-- un territoire pilote est une ligne de cette table, pas une branche de code.
-- =============================================================================

create table app.territories (
  id uuid primary key default gen_random_uuid(),
  parent_id uuid references app.territories (id) on delete restrict,
  type app.territory_type not null,
  code text not null,
  slug text not null unique,
  name text not null,
  short_name text,
  timezone text not null default 'Europe/Paris',
  geometry extensions.geometry(MultiPolygon, 4326),
  center extensions.geometry(Point, 4326) not null,
  default_zoom numeric(4, 2) not null default 8.0,
  status app.territory_status not null default 'draft',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint territories_code_type_unique unique (type, code),
  constraint territories_slug_format check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint territories_zoom_range check (default_zoom >= 0 and default_zoom <= 22),
  constraint territories_no_self_parent check (parent_id is null or parent_id <> id)
);

comment on table app.territories is
  'Régions, départements et collectivités configurés. Cahier §13.1.';
comment on column app.territories.settings is
  'Options contrôlées : tampon frontalier, avertissements locaux, libellés.';

create index territories_parent_idx on app.territories (parent_id);
create index territories_status_idx on app.territories (status);
create index territories_geometry_gix on app.territories using gist (geometry);

create trigger territories_set_updated_at
  before update on app.territories
  for each row execute function app.set_updated_at();

alter table app.territories enable row level security;

-- =============================================================================
-- Communes
-- =============================================================================

create table geo.municipalities (
  insee_code text primary key,
  department_code text not null,
  name text not null,
  -- Forme normalisée sans accent ni ponctuation, alimentée par trigger.
  normalized_name text not null,
  postal_codes text[] not null default '{}',
  geometry extensions.geometry(MultiPolygon, 4326) not null,
  centroid extensions.geometry(Point, 4326) not null,
  area_km2 numeric(12, 4),
  source_version text not null,
  valid_from date not null,
  valid_to date,

  constraint municipalities_insee_format check (insee_code ~ '^(?:[0-9]{5}|2[AB][0-9]{3})$'),
  constraint municipalities_validity check (valid_to is null or valid_to > valid_from)
);

comment on table geo.municipalities is
  'Limites communales IGN ADMIN EXPRESS COG, versionnées. Cahier §13.2 et §9.5.';
comment on column geo.municipalities.valid_to is
  'Fin de validité d''une commune fusionnée ou supprimée. Les données historiques ne sont pas effacées.';

create index municipalities_department_idx on geo.municipalities (department_code);
create index municipalities_geometry_gix on geo.municipalities using gist (geometry);
create index municipalities_centroid_gix on geo.municipalities using gist (centroid);
create index municipalities_postal_codes_gin on geo.municipalities using gin (postal_codes);

-- Recherche tolérante aux fautes de frappe et aux accents. FR-020
create index municipalities_normalized_name_trgm
  on geo.municipalities using gin (normalized_name extensions.gin_trgm_ops);

-- Seules les communes en vigueur sont proposées à la recherche.
create index municipalities_current_idx on geo.municipalities (name) where valid_to is null;

alter table geo.municipalities enable row level security;

-- L'extension `unaccent` dépend d'un dictionnaire et n'est pas immuable, donc
-- pas indexable directement. On translittère explicitement les caractères
-- rencontrés dans les toponymes français.
create or replace function geo.unaccent_fr(value text)
returns text
language sql
immutable
strict
as $$
  select translate(
    value,
    'àáâãäåçèéêëìíîïñòóôõöùúûüýÿÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝŸœŒæÆ',
    'aaaaaaceeeeiiiinooooouuuuyyAAAAAACEEEEIIIINOOOOOUUUUYYooaA'
  );
$$;

-- Normalisation : minuscules, sans accents, tirets et apostrophes ramenés à des
-- espaces. « Saint-Étienne-de-Tinée » et « saint etienne de tinee » doivent se
-- rejoindre. FR-020
create or replace function geo.normalize_name(value text)
returns text
language sql
immutable
strict
set search_path = geo, pg_temp
as $$
  select btrim(
    regexp_replace(lower(geo.unaccent_fr(value)), '[^a-z0-9]+', ' ', 'g')
  );
$$;

create or replace function geo.set_normalized_name()
returns trigger
language plpgsql
set search_path = geo, pg_temp
as $$
begin
  new.normalized_name = geo.normalize_name(new.name);
  return new;
end;
$$;

create trigger municipalities_set_normalized_name
  before insert or update of name on geo.municipalities
  for each row execute function geo.set_normalized_name();
