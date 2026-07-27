-- =============================================================================
-- Registre des sources — données de référence
--
-- Cahier §9.7 et §16.8. Les intervalles reprennent le calendrier d'orchestration.
-- Aucune clé API ici : elles vivent dans l'environnement du worker (§14.3).
-- =============================================================================

insert into ingest.data_sources
  (key, name, provider, expected_interval, stale_after, documentation_url,
   license_name, attribution, retention_policy, settings)
values
  (
    'firms',
    'NASA FIRMS — détections de feux actifs',
    'NASA / MODAPS',
    interval '10 minutes',
    interval '6 hours',
    'https://firms.modaps.eosdis.nasa.gov/api/area/',
    'NASA Open Data',
    'Données de feux actifs fournies par NASA FIRMS',
    'Fichiers bruts 30 jours minimum ; détections conservées',
    jsonb_build_object(
      'sensors', jsonb_build_array('VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT', 'MODIS_NRT'),
      'quota_transactions_per_10min', 5000,
      'poll_interval_minutes', 10
    )
  ),
  (
    'arome',
    'Météo-France — modèle AROME',
    'Météo-France',
    interval '3 hours',
    interval '9 hours',
    'https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=131&id_rubrique=51',
    'Licence Ouverte / Etalab',
    'Données météorologiques Météo-France (modèle AROME)',
    'GRIB2 bruts 30 jours',
    jsonb_build_object('parameters', jsonb_build_array('u10', 'v10'), 'catalog_poll_minutes', 30)
  ),
  (
    'cams',
    'Copernicus CAMS — qualité de l''air Europe',
    'Copernicus / ECMWF',
    interval '24 hours',
    interval '48 hours',
    'https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts',
    'Copernicus Licence',
    'Généré avec les services Copernicus Atmosphere Monitoring Service',
    'NetCDF bruts 30 jours ; tuiles courantes',
    jsonb_build_object('pollutants', jsonb_build_array('pm2p5', 'pm10'), 'resolution_deg', 0.1)
  ),
  (
    'radar',
    'Météo-France — radar de précipitations',
    'Météo-France',
    interval '5 minutes',
    interval '1 hour',
    'https://donneespubliques.meteofrance.fr/',
    'Licence Ouverte / Etalab',
    'Données radar Météo-France',
    'Frames conservées 6 à 24 heures',
    jsonb_build_object('frame_retention_hours', 24, 'max_client_frames', 24)
  ),
  (
    'ign_admin_express',
    'IGN — ADMIN EXPRESS COG',
    'IGN / Géoplateforme',
    interval '30 days',
    interval '400 days',
    'https://geoservices.ign.fr/telechargement-api',
    'Licence Ouverte / Etalab',
    'Limites administratives © IGN — ADMIN EXPRESS COG',
    'Versions conservées pour reproductibilité',
    jsonb_build_object('rate_limit_rps', 10, 'import_mode', 'manual')
  )
on conflict (key) do nothing;
