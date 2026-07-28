-- =============================================================================
-- FIXTURE DE DÉVELOPPEMENT — NE JAMAIS APPLIQUER EN PRODUCTION
--
-- Jeu de démonstration permettant de développer la fiche événement avant que
-- l'ingestion FIRMS ne soit en service (jalon J1 du plan de développement).
--
-- Ce fichier n'est PAS dans `supabase/seed/*.sql` : le glob du seed nominal ne
-- descend pas dans `dev/`, et `scripts/apply-seed.py` exige `--dev` pour
-- l'appliquer. Un jeu de détections inventé, affiché sans distinction dans une
-- commune réelle, serait exactement la désinformation que le cahier §2.4
-- cherche à éviter.
--
-- Garde-fous :
--   - identifiant public préfixé DEMO, visible dans l'URL et sur la fiche ;
--   - clés fournisseur préfixées `demo:`, ce qui les rend repérables et
--     supprimables en une requête ;
--   - le script commence par supprimer toute fixture antérieure : il est
--     rejouable et ne laisse jamais deux jeux superposés.
--
-- Suppression :
--   delete from fire.events where public_id like 'DEMO-%';
--   delete from fire.detections where provider_key like 'demo:%';
-- =============================================================================

do $$
declare
  v_source_id uuid;
  v_territory_id uuid;
  v_event_id uuid;
  v_insee text;
  v_point extensions.geometry(Point, 4326);
  v_detection record;
  v_first timestamptz := timestamptz '2026-07-25 10:12:00+00';
  v_last timestamptz := timestamptz '2026-07-25 22:04:00+00';
begin
  -- Nettoyage d'une exécution précédente. Les détections ne cascadent pas
  -- depuis l'événement : elles sont supprimées explicitement.
  delete from fire.events where public_id like 'DEMO-%';
  delete from fire.detections where provider_key like 'demo:%';

  select id into v_source_id from ingest.data_sources where key = 'firms';
  if v_source_id is null then
    raise exception 'Seed nominal absent : appliquer d''abord supabase/seed/.';
  end if;

  select id into v_territory_id
  from app.territories
  where type = 'department' and code = '83';

  -- Arrière-pays varois, à l'écart des zones densément habitées.
  v_point := extensions.st_setsrid(extensions.st_makepoint(6.3520, 43.4610), 4326);

  -- Détections membres. Deux capteurs, trois satellites, sur douze heures.
  for v_detection in
    select *
    from (values
      ('demo:1', 'VIIRS', 'N20',   timestamptz '2026-07-25 10:12:00+00', 6.3512, 43.4602, 0.62,  4.1, 331.2, 'D'),
      ('demo:2', 'VIIRS', 'N20',   timestamptz '2026-07-25 10:12:00+00', 6.3548, 43.4631, 0.90, 12.7, 348.9, 'D'),
      ('demo:3', 'MODIS', 'Terra', timestamptz '2026-07-25 12:41:00+00', 6.3505, 43.4598, 0.78,  9.8, 322.4, 'D'),
      ('demo:4', 'VIIRS', 'N21',   timestamptz '2026-07-25 13:55:00+00', 6.3561, 43.4644, 0.90, 23.4, 361.7, 'D'),
      ('demo:5', 'VIIRS', 'N21',   timestamptz '2026-07-25 13:55:00+00', 6.3499, 43.4589, 0.60,  7.2, 329.0, 'D'),
      ('demo:6', 'VIIRS', 'N20',   timestamptz '2026-07-25 21:48:00+00', 6.3534, 43.4618, 0.60,  5.6, 318.3, 'N'),
      ('demo:7', 'VIIRS', 'N20',   timestamptz '2026-07-25 22:04:00+00', 6.3527, 43.4609, 0.25,  4.4, 311.5, 'N')
    ) as t(provider_key, sensor, satellite, acquired_at, lon, lat, confidence, frp, brightness, day_night)
  loop
    insert into fire.detections (
      provider_key, source_id, sensor, satellite, product_version,
      acquired_at, location, latitude, longitude,
      confidence_raw, confidence_score, frp_mw, brightness, day_night,
      scan_km, track_km, raw_payload, is_public
    )
    values (
      v_detection.provider_key, v_source_id, v_detection.sensor, v_detection.satellite,
      'DEMO', v_detection.acquired_at,
      extensions.st_setsrid(extensions.st_makepoint(v_detection.lon, v_detection.lat), 4326),
      v_detection.lat, v_detection.lon,
      'demo', v_detection.confidence, v_detection.frp, v_detection.brightness,
      v_detection.day_night, 0.39, 0.36,
      jsonb_build_object('fixture', true, 'note', 'jeu de démonstration, aucune observation réelle'),
      true
    );
  end loop;

  -- Commune la plus proche, résolue par PostGIS plutôt que codée en dur :
  -- la fixture reste correcte si le référentiel communal change.
  select m.insee_code into v_insee
  from geo.municipalities m
  where m.valid_to is null
  order by m.geometry <-> v_point
  limit 1;

  insert into fire.events (
    public_id, freshness_status, verification_status,
    first_detected_at, last_detected_at, representative_point,
    detection_count, sensor_count, confidence_level, confidence_score,
    frp_min_mw, frp_median_mw, frp_max_mw,
    nearest_municipality_code, territory_id, algorithm_version
  )
  values (
    'DEMO-2607A1', 'not_recent', 'probable_event',
    v_first, v_last, v_point,
    7, 2, 'medium', 0.62,
    4.1, 7.2, 23.4,
    v_insee, v_territory_id, 'demo-fixture'
  )
  returning id into v_event_id;

  insert into fire.event_detections (
    event_id, detection_id, detection_acquired_at, method, score, algorithm_version
  )
  select v_event_id, d.id, d.acquired_at, 'auto', 0.9, 'demo-fixture'
  from fire.detections d
  where d.provider_key like 'demo:%';

  -- Chronologie. Chaque entrée porte sa provenance : une observation et un
  -- regroupement algorithmique ne se présentent pas de la même façon (§5.7).
  insert into fire.event_timeline_entries (
    event_id, entry_type, provenance, occurred_at, title, summary,
    visibility, deduplication_key
  )
  values
    (v_event_id, 'detection', 'observation', v_first,
     'Première détection thermique',
     'Deux anomalies thermiques observées par VIIRS sur NOAA-20.',
     'public', 'demo:first'),
    (v_event_id, 'grouping', 'algorithmic_inference',
     v_first + interval '4 minutes',
     'Regroupement en événement probable',
     'Les détections proches dans l''espace et le temps ont été regroupées par l''algorithme de rattachement.',
     'public', 'demo:grouping'),
    (v_event_id, 'detection', 'observation',
     timestamptz '2026-07-25 13:55:00+00',
     'Confirmation par un second capteur',
     'Nouvelles détections VIIRS sur NOAA-21, cohérentes avec les précédentes.',
     'public', 'demo:second-sensor'),
    (v_event_id, 'detection', 'observation', v_last,
     'Dernière observation',
     'Détection nocturne de faible intensité. Aucune observation ultérieure.',
     'public', 'demo:last');

  raise notice 'Fixture DEMO-2607A1 créée, commune la plus proche : %', v_insee;
end $$;
