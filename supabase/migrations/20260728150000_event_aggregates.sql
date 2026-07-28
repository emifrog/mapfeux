-- =============================================================================
-- 20260728150000 — Recalcul des agrégats d'un événement
--
-- Cahier §13.6 et §17.2, étape 7.
--
-- Les agrégats sont recalculés en base plutôt qu'en Python : ils dérivent
-- entièrement des détections membres, et les faire voyager jusqu'au worker pour
-- les renvoyer aussitôt serait un aller-retour sans objet. Le calcul est de
-- surcroît atomique, donc jamais observable à moitié fait.
--
-- La fonction retourne les grandeurs nécessaires au score de fiabilité, qui est
-- calculé côté worker : sa formule est versionnée et testée unitairement, ce
-- qu'une expression SQL enfouie dans une vue ne permettrait pas (§17.3).
-- =============================================================================

create or replace function fire.recompute_event_aggregates(target_event_id uuid)
returns table (
  detection_count integer,
  sensor_count integer,
  mean_confidence numeric,
  known_source_count integer,
  span_hours numeric
)
language plpgsql
security definer
set search_path = fire, geo, extensions, pg_temp
as $$
declare
  v_stats record;
begin
  select
    count(*)::integer as n,
    count(distinct d.sensor)::integer as sensors,
    min(d.acquired_at) as first_at,
    max(d.acquired_at) as last_at,
    avg(d.confidence_score) as mean_conf,
    count(*) filter (where d.known_source_id is not null)::integer as known,
    min(d.frp_mw) as frp_min,
    max(d.frp_mw) as frp_max,
    percentile_cont(0.5) within group (order by d.frp_mw) as frp_median,
    extensions.st_centroid(extensions.st_collect(d.location)) as centre,
    -- Enveloppe : l'enveloppe convexe des pixels, dilatée d'un demi-pixel VIIRS.
    -- Sans dilatation, une détection isolée produirait un point et deux
    -- détections une ligne, que la colonne MultiPolygon refuserait.
    extensions.st_multi(
      extensions.st_collectionextract(
        extensions.st_makevalid(
          extensions.st_buffer(
            extensions.st_convexhull(extensions.st_collect(d.location))::extensions.geography,
            190
          )::extensions.geometry
        ),
        3
      )
    ) as envelope
  into v_stats
  from fire.event_detections ed
  join fire.detections d
    on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
  where ed.event_id = target_event_id
    and d.is_public;

  if v_stats.n is null or v_stats.n = 0 then
    raise exception 'Événement % sans détection membre publiable.', target_event_id;
  end if;

  update fire.events e
  set
    detection_count = v_stats.n,
    sensor_count = v_stats.sensors,
    first_detected_at = v_stats.first_at,
    last_detected_at = v_stats.last_at,
    representative_point = v_stats.centre,
    extent = v_stats.envelope,
    frp_min_mw = v_stats.frp_min,
    frp_median_mw = v_stats.frp_median,
    frp_max_mw = v_stats.frp_max,
    nearest_municipality_code = (
      select m.insee_code
      from geo.municipalities m
      where m.valid_to is null
      order by m.geometry <-> v_stats.centre
      limit 1
    ),
    territory_id = (
      select t.id
      from app.territories t
      where t.type = 'department'
        and t.code = (
          select m.department_code
          from geo.municipalities m
          where m.valid_to is null
          order by m.geometry <-> v_stats.centre
          limit 1
        )
      limit 1
    )
  where e.id = target_event_id;

  return query
  select
    v_stats.n,
    v_stats.sensors,
    v_stats.mean_conf,
    v_stats.known,
    round(extract(epoch from (v_stats.last_at - v_stats.first_at)) / 3600.0, 3);
end;
$$;

comment on function fire.recompute_event_aggregates is
  'Recalcule les agrégats d''un événement et retourne les grandeurs du score de fiabilité (§17.2).';
