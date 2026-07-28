-- =============================================================================
-- 20260728110000 — Surface publique de la fiche événement
--
-- Cahier §5.6, §15.2 et §13.9.
--
-- La fiche est l'objet central du produit. Elle doit être rendue côté serveur
-- en une poignée de requêtes, sans dépendre de la carte ni de JavaScript
-- (FR-051), d'où des fonctions qui retournent tout le nécessaire d'un coup
-- plutôt qu'une vue à recomposer côté application.
--
-- Aucune de ces fonctions n'expose `raw_payload`, `manual_state`,
-- `hidden_reason`, `confidence_score` interne ni l'identité des opérateurs.
-- Le score 0-1 reste interne ; seul le niveau public est publié (§17.3).
-- =============================================================================

create or replace function api.fire_event(event_public_id text)
returns table (
  public_id text,
  freshness_status fire.freshness_status,
  verification_status fire.verification_status,
  official_control_status fire.official_control_status,
  official_status_at timestamptz,
  official_organisation text,
  official_source_url text,
  first_detected_at timestamptz,
  last_detected_at timestamptz,
  longitude double precision,
  latitude double precision,
  detection_count integer,
  sensor_count integer,
  sensors text[],
  satellites text[],
  confidence_level app.confidence_level,
  frp_min_mw numeric,
  frp_median_mw numeric,
  frp_max_mw numeric,
  nearest_municipality_code text,
  nearest_municipality_name text,
  territory_slug text,
  territory_name text,
  territory_timezone text,
  last_public_snapshot_at timestamptz,
  updated_at timestamptz,
  timeline_entry_count integer,
  timeline_latest_at timestamptz
)
language sql
stable
security definer
set search_path = fire, app, geo, extensions, pg_temp
as $$
  select
    e.public_id,
    e.freshness_status,
    e.verification_status,
    e.official_control_status,
    e.official_status_at,
    om.organisation,
    om.source_url,
    e.first_detected_at,
    e.last_detected_at,
    extensions.st_x(e.representative_point),
    extensions.st_y(e.representative_point),
    e.detection_count,
    e.sensor_count,
    coalesce(members.sensors, '{}'),
    coalesce(members.satellites, '{}'),
    e.confidence_level,
    e.frp_min_mw,
    e.frp_median_mw,
    e.frp_max_mw,
    e.nearest_municipality_code,
    m.name,
    t.slug,
    t.name,
    coalesce(t.timezone, 'Europe/Paris'),
    e.last_public_snapshot_at,
    e.updated_at,
    coalesce(tl.entry_count, 0)::integer,
    tl.latest_at
  from fire.events e
  left join geo.municipalities m on m.insee_code = e.nearest_municipality_code
  left join app.territories t on t.id = e.territory_id
  left join app.official_messages om on om.id = e.official_status_source_id
  left join lateral (
    select
      array_agg(distinct d.sensor order by d.sensor) as sensors,
      array_agg(distinct d.satellite order by d.satellite) as satellites
    from fire.event_detections ed
    join fire.detections d
      on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
    where ed.event_id = e.id
      and d.is_public
  ) members on true
  left join lateral (
    select count(*) as entry_count, max(te.occurred_at) as latest_at
    from fire.event_timeline_entries te
    where te.event_id = e.id and te.visibility = 'public'
  ) tl on true
  where e.public_id = event_public_id
    -- Un événement masqué n'existe pas pour le public, y compris par son URL
    -- directe. Le masquage n'est pas une simple absence de la carte (§17.7).
    and e.freshness_status <> 'hidden';
$$;

comment on function api.fire_event is
  'Fiche événement complète en une requête. Cahier §5.6.';

-- =============================================================================
-- Détections membres
-- =============================================================================

create or replace function api.fire_event_detections(
  event_public_id text,
  max_results integer default 500
)
returns table (
  acquired_at timestamptz,
  sensor text,
  satellite text,
  longitude double precision,
  latitude double precision,
  confidence_level text,
  frp_mw numeric,
  day_night char(1),
  is_known_thermal_source boolean
)
language sql
stable
security definer
set search_path = fire, extensions, pg_temp
as $$
  select
    d.acquired_at,
    d.sensor,
    d.satellite,
    extensions.st_x(d.location),
    extensions.st_y(d.location),
    -- La confiance fournisseur brute n'est pas publiée telle quelle : elle
    -- n'a pas le même sens entre VIIRS et MODIS. Seul le niveau normalisé
    -- sort, et « inconnu » reste « inconnu » (§17.3).
    case
      when d.confidence_score is null then 'unknown'
      when d.confidence_score >= 0.8 then 'high'
      when d.confidence_score >= 0.5 then 'medium'
      else 'low'
    end,
    d.frp_mw,
    d.day_night,
    d.known_source_id is not null
  from fire.event_detections ed
  join fire.events e on e.id = ed.event_id
  join fire.detections d
    on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and d.is_public
  order by d.acquired_at desc
  limit least(greatest(coalesce(max_results, 500), 1), 2000);
$$;

comment on function api.fire_event_detections is
  'Détections membres d''un événement. raw_payload n''est jamais exposé (ADR-004).';

grant execute on function
  api.fire_event(text),
  api.fire_event_detections(text, integer)
to anon, authenticated;
