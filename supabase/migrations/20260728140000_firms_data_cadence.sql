-- =============================================================================
-- 20260728140000 — Cadence attendue des données FIRMS
--
-- Cahier §13.3 et §9.1.
--
-- Défaut constaté au premier import réel : FIRMS était affichée « retardée »
-- alors que l'import venait de réussir sur des données de la mi-journée.
--
-- `expected_interval` était renseigné à dix minutes, qui est la **cadence
-- d'interrogation** de l'API. Or la vue `api.source_status` compare ce seuil à
-- l'âge de la **donnée**, pas à celui de l'appel. Les satellites polaires
-- passent toutes les quelques heures sur la France, et FIRMS annonce une mise à
-- disposition en général sous trois heures : une donnée vieille de deux heures
-- est parfaitement normale.
--
-- Conserver dix minutes aurait affiché « retardée » en permanence, ce qui vide
-- l'indicateur de son sens : un signal toujours allumé n'est plus un signal.
--
-- Nouvelles valeurs, pour la constellation VIIRS à trois satellites survolant
-- la France de jour comme de nuit, latence NRT comprise :
--   expected_interval  6 heures   — au-delà, une donnée manque probablement
--   stale_after       24 heures   — au-delà, la source ne peut plus être
--                                   présentée comme représentative
-- =============================================================================

update ingest.data_sources
set
  expected_interval = interval '6 hours',
  stale_after = interval '24 hours'
where key = 'firms';

comment on column ingest.data_sources.expected_interval is
  'Intervalle attendu entre deux DONNÉES, pas entre deux appels. La cadence d''interrogation vit dans settings.';
