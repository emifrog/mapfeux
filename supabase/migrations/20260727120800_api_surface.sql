-- =============================================================================
-- 20260727120800 — Surface publique `api`
--
-- Cahier §12.1, §14.2 et §15.2.
--
-- Choix de sécurité assumé : les vues de ce schéma appartiennent au propriétaire
-- de la base et s'exécutent donc avec ses droits (security_invoker désactivé,
-- comportement par défaut). C'est ce qui leur permet de lire les schémas
-- internes auxquels `anon` n'a aucun accès. La conséquence est que le filtrage
-- public est porté par la définition de chaque vue, et non par une politique
-- RLS : toute modification de ces vues est une modification de périmètre public
-- et doit être revue comme telle.
--
-- Aucune de ces vues n'expose raw_payload, error_summary, internal_notes,
-- hidden_reason ni l'identité des opérateurs. §14.2
-- =============================================================================

-- =============================================================================
-- Territoires
-- =============================================================================

create view api.territories as
select
  t.slug,
  t.code,
  t.type,
  t.name,
  t.short_name,
  parent.slug as parent_slug,
  t.status,
  t.timezone,
  extensions.st_x(t.center) as center_longitude,
  extensions.st_y(t.center) as center_latitude,
  t.default_zoom
from app.territories t
left join app.territories parent on parent.id = t.parent_id
-- Les territoires en préparation restent invisibles ; « à venir » se configure
-- avec le statut `pilot`, sans code spécifique. FR-014
where t.status in ('pilot', 'active');

comment on view api.territories is
  'Hiérarchie territoriale publiable. Cahier §15.2.';

-- =============================================================================
-- Liens officiels
-- =============================================================================

create view api.official_links as
select
  t.slug as territory_slug,
  l.category,
  l.title,
  l.url,
  l.organisation,
  l.display_order
from app.official_links l
join app.territories t on t.id = l.territory_id
where l.is_active
  and t.status in ('pilot', 'active');

-- =============================================================================
-- État des sources
-- =============================================================================

create view api.source_status as
with last_success as (
  select distinct on (r.source_id)
    r.source_id,
    r.finished_at,
    r.source_data_at
  from ingest.import_runs r
  where r.status in ('success', 'partial')
  order by r.source_id, r.finished_at desc
),
open_incident as (
  select distinct on (i.source_id)
    i.source_id,
    i.public_message,
    i.opened_at
  from ingest.incidents i
  where i.resolved_at is null
  order by i.source_id, i.opened_at desc
)
select
  s.key,
  s.name,
  s.provider,
  s.attribution,
  s.documentation_url,
  s.license_name,
  ls.finished_at as last_successful_import_at,
  ls.source_data_at as last_data_at,
  case
    when s.status = 'disabled' then 'maintenance'
    when s.status = 'paused' then 'maintenance'
    when ls.source_data_at is null then 'unavailable'
    when now() - ls.source_data_at >= s.stale_after then 'stale'
    when now() - ls.source_data_at >= s.expected_interval then 'delayed'
    else 'fresh'
  end as freshness,
  oi.public_message as incident_message,
  oi.opened_at as incident_opened_at
from ingest.data_sources s
left join last_success ls on ls.source_id = s.id
left join open_incident oi on oi.source_id = s.id;

comment on view api.source_status is
  'Alimente /statut. Les messages d''erreur techniques restent internes (FR-112).';

-- =============================================================================
-- Événements
-- =============================================================================

-- Vue de base : filtre unique du périmètre public des événements. Toute
-- fonction publique s'appuie dessus plutôt que sur fire.events.
create view api.fire_events as
select
  e.id,
  e.public_id,
  e.freshness_status,
  e.verification_status,
  e.official_control_status,
  e.official_status_at,
  e.first_detected_at,
  e.last_detected_at,
  extensions.st_x(e.representative_point) as longitude,
  extensions.st_y(e.representative_point) as latitude,
  e.detection_count,
  e.sensor_count,
  e.confidence_level,
  e.frp_min_mw,
  e.frp_median_mw,
  e.frp_max_mw,
  e.nearest_municipality_code,
  m.name as nearest_municipality_name,
  t.slug as territory_slug,
  e.last_public_snapshot_at,
  e.updated_at
from fire.events e
left join geo.municipalities m on m.insee_code = e.nearest_municipality_code
left join app.territories t on t.id = e.territory_id
where e.freshness_status <> 'hidden';

comment on view api.fire_events is
  'Événements publiables. Le score interne 0-1 n''est jamais exposé (§17.3).';

-- Recherche par emprise. Les bornes sont validées ici et non seulement côté
-- application : la fonction est appelable directement par la Data API. §21.4
create or replace function api.fires_in_bbox(
  min_lon double precision,
  min_lat double precision,
  max_lon double precision,
  max_lat double precision,
  since timestamptz default null,
  max_results integer default 200
)
returns setof api.fire_events
language plpgsql
stable
security definer
set search_path = api, fire, extensions, pg_temp
as $$
declare
  max_area_deg2 constant double precision := 30;
begin
  if min_lon is null or min_lat is null or max_lon is null or max_lat is null then
    raise exception 'INVALID_BBOX' using errcode = 'invalid_parameter_value';
  end if;

  if min_lon >= max_lon or min_lat >= max_lat
     or min_lon < -180 or max_lon > 180
     or min_lat < -90 or max_lat > 90 then
    raise exception 'INVALID_BBOX' using errcode = 'invalid_parameter_value';
  end if;

  if (max_lon - min_lon) * (max_lat - min_lat) > max_area_deg2 then
    raise exception 'BBOX_TOO_LARGE' using errcode = 'invalid_parameter_value';
  end if;

  return query
  select v.*
  from api.fire_events v
  join fire.events e on e.id = v.id
  where e.representative_point && extensions.st_makeenvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    and (since is null or e.last_detected_at >= since)
  order by e.last_detected_at desc
  limit least(greatest(coalesce(max_results, 200), 1), 500);
end;
$$;

-- Chronologie publique d'un événement. Les entrées internes et retirées ne
-- sortent jamais de la base. §5.7
create or replace function api.fire_event_timeline(event_public_id text)
returns table (
  id uuid,
  entry_type fire.timeline_entry_type,
  provenance app.provenance,
  occurred_at timestamptz,
  recorded_at timestamptz,
  title text,
  summary text,
  source_organisation text,
  source_url text
)
language sql
stable
security definer
set search_path = fire, app, pg_temp
as $$
  select
    te.id,
    te.entry_type,
    te.provenance,
    te.occurred_at,
    te.recorded_at,
    te.title,
    te.summary,
    om.organisation,
    om.source_url
  from fire.event_timeline_entries te
  join fire.events e on e.id = te.event_id
  left join app.official_messages om on om.id = te.source_id
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and te.visibility = 'public'
  order by te.occurred_at desc, te.recorded_at desc;
$$;

-- Résolution d'un identifiant fusionné vers l'événement canonique. §13.10
create or replace function api.resolve_event_alias(candidate_public_id text)
returns text
language sql
stable
security definer
set search_path = fire, pg_temp
as $$
  select coalesce(
    (select e.public_id from fire.events e where e.public_id = candidate_public_id),
    (select canonical.public_id
     from fire.event_aliases a
     join fire.events canonical on canonical.id = a.canonical_event_id
     where a.public_id = candidate_public_id)
  );
$$;

-- =============================================================================
-- Communes
-- =============================================================================

create or replace function api.search_municipalities(q text, max_results integer default 10)
returns table (
  insee_code text,
  name text,
  department_code text,
  postal_codes text[],
  longitude double precision,
  latitude double precision
)
language sql
stable
security definer
set search_path = geo, extensions, pg_temp
as $$
  with needle as (
    select geo.normalize_name(coalesce(q, '')) as value
  )
  select
    m.insee_code,
    m.name,
    m.department_code,
    m.postal_codes,
    extensions.st_x(m.centroid),
    extensions.st_y(m.centroid)
  from geo.municipalities m, needle n
  where m.valid_to is null
    and length(n.value) >= 1
    and (
      m.normalized_name like n.value || '%'
      or m.normalized_name % n.value
      or q = any (m.postal_codes)
    )
  order by
    (m.normalized_name = n.value) desc,
    (m.normalized_name like n.value || '%') desc,
    extensions.similarity(m.normalized_name, n.value) desc,
    m.name
  limit least(greatest(coalesce(max_results, 10), 1), 25);
$$;

comment on function api.search_municipalities is
  'Recherche tolérante par nom ou code postal, code INSEE comme identifiant de référence (FR-020).';

-- Résolution point vers commune. Les coordonnées ne sont ni conservées ni
-- journalisées : la fonction ne fait que lire. §22.2
create or replace function api.resolve_municipality(
  lon double precision,
  lat double precision
)
returns table (
  insee_code text,
  name text,
  department_code text
)
language plpgsql
stable
security definer
set search_path = geo, extensions, pg_temp
as $$
begin
  if lon is null or lat is null or lon < -180 or lon > 180 or lat < -90 or lat > 90 then
    raise exception 'VALIDATION_ERROR' using errcode = 'invalid_parameter_value';
  end if;

  return query
  select m.insee_code, m.name, m.department_code
  from geo.municipalities m
  where m.valid_to is null
    and extensions.st_covers(
      m.geometry,
      extensions.st_setsrid(extensions.st_makepoint(lon, lat), 4326)
    )
  -- Un point exactement sur une limite peut appartenir à deux polygones :
  -- on retient la commune dont le centre est le plus proche. §24.3
  order by m.centroid <-> extensions.st_setsrid(extensions.st_makepoint(lon, lat), 4326)
  limit 1;
end;
$$;

-- =============================================================================
-- Droits
-- =============================================================================

grant select on
  api.territories,
  api.official_links,
  api.source_status,
  api.fire_events
to anon, authenticated;

grant execute on function
  api.fires_in_bbox(double precision, double precision, double precision, double precision, timestamptz, integer),
  api.fire_event_timeline(text),
  api.resolve_event_alias(text),
  api.search_municipalities(text, integer),
  api.resolve_municipality(double precision, double precision)
to anon, authenticated;

-- Aucun droit d'écriture, sur aucun objet public.
revoke insert, update, delete on all tables in schema api from anon, authenticated;
