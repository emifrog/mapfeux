-- =============================================================================
-- Registre des sources — données de référence
--
-- Cahier §9.7 et §16.8.
--
-- `expected_interval` et `stale_after` portent sur l'âge de la **donnée**, pas
-- sur la cadence d'interrogation, qui vit dans `settings`. Pour FIRMS, les deux
-- diffèrent d'un ordre de grandeur : on interroge toutes les dix minutes, mais
-- les satellites polaires ne repassent que toutes les quelques heures.
--
-- Aucune clé API ici : elles vivent dans l'environnement du worker (§14.3).
-- =============================================================================

-- `status` est renseigné explicitement, colonne comprise.
--
-- Un connecteur qui n'existe pas encore se déclare `disabled` — /statut lit
-- alors « À venir » (FR-150), jamais le mot d'une panne. La mise en service
-- passe le statut à `active` **ici et en production** : le seed est en
-- `on conflict do nothing`, le rejouer ne modifie jamais une ligne existante
-- — l'UPDATE en production est un geste d'exploitation distinct, consigné au
-- plan. CAMS et le radar sont en service depuis le 26 août 2026, premières
-- passes planifiées constatées.
--
-- Le statut vit ici, et non dans une migration seule : les migrations
-- s'appliquent **avant** le seed, si bien qu'un `update` sur une base vierge ne
-- toucherait aucune ligne.
insert into ingest.data_sources
  (key, name, provider, status, expected_interval, stale_after, documentation_url,
   license_name, attribution, retention_policy, settings)
values
  (
    'firms',
    'NASA FIRMS — détections de feux actifs',
    'NASA / MODAPS',
    'active',
    interval '6 hours',
    interval '24 hours',
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
    'vigilance',
    'Météo-France — vigilance météorologique',
    'Météo-France',
    'active',
    -- Diffusion nominale à 6 h et 16 h locales, et davantage si la situation
    -- l'exige. Un bulletin vieux de plus de vingt heures signale une panne, pas
    -- une accalmie.
    interval '12 hours',
    interval '20 hours',
    'https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesVigilance',
    'Licence Ouverte Etalab v2',
    'Source : Météo-France',
    'Bulletins bruts conservés ; niveaux conservés',
    jsonb_build_object(
      'format', 'V6',
      'domain', 'FRA',
      'poll_interval_minutes', 60,
      'phenomena_relevant_to_fire', jsonb_build_array(1, 3, 6),
      -- Voie nominale : l'API temps réel, avec clé. Le dépôt objet de
      -- data.gouv.fr sert le même produit sans clé, mais c'est une **archive**
      -- — environ un jour de retard, mesuré le 6 août. Employé en repli, il
      -- ferait afficher « trop ancienne » en permanence, et l'ingestion le dit.
      'access', 'temps-reel',
      'endpoint', 'https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours',
      'rate_limit_per_minute', 60,
      'fallback', 'depot-objet-data-gouv-archive',
      'fallback_lag_hours', 24
    )
  ),
  (
    'arome',
    'Météo-France — modèle AROME',
    'Météo-France',
    'active',
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
    -- En service depuis le 26 août 2026 : chaîne complète (import, COG,
    -- tuiles, fiche commune, couche carte) et première passe planifiée
    -- constatée.
    'active',
    interval '24 hours',
    interval '48 hours',
    'https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts',
    'Copernicus Licence',
    'Généré avec les services Copernicus Atmosphere Monitoring Service',
    'NetCDF bruts 30 jours ; tuiles courantes',
    -- Clés de polluants : celles du registre air.grid_assets et du code.
    jsonb_build_object('pollutants', jsonb_build_array('pm2_5', 'pm10'), 'resolution_deg', 0.1)
  ),
  (
    'radar',
    'Météo-France — radar de précipitations',
    'Météo-France',
    -- En service depuis le 26 août 2026 (mosaïque lame d'eau 500 m, HDF5
    -- ODIM via DPRadar). Les intervalles décrivent l'âge de la donnée que
    -- NOTRE chaîne peut promettre, pas la cadence du produit : le produit
    -- paraît toutes les cinq minutes, mais GitHub Actions étrangle les
    -- crons `*/5` à ~une passe par heure (mesuré les 25-26 août : 06:21,
    -- 07:22, 08:06). Annoncer cinq minutes afficherait « En retard » en
    -- permanence — un signal exact et faux, la leçon de la vigilance.
    -- L'ordonnancement propre (§8.1) ramènera ces bornes aux cinq minutes.
    'active',
    interval '1 hour',
    interval '3 hours',
    'https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesRadar',
    'Licence Ouverte / Etalab',
    'Données radar Météo-France',
    'Frames : brut archivé, image web expirée à 2 h',
    jsonb_build_object('frame_retention_hours', 2, 'max_client_frames', 24)
  ),
  (
    'ign_admin_express',
    'IGN — ADMIN EXPRESS COG',
    'IGN / Géoplateforme',
    'active',
    interval '30 days',
    interval '400 days',
    'https://geoservices.ign.fr/telechargement-api',
    'Licence Ouverte / Etalab',
    'Limites administratives © IGN — ADMIN EXPRESS COG',
    'Versions conservées pour reproductibilité',
    jsonb_build_object('rate_limit_rps', 10, 'import_mode', 'manual')
  )
on conflict (key) do nothing;
