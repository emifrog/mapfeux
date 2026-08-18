-- =============================================================================
-- 20260818100000 — Clé d'upsert des échantillons de vent (jalon J8)
--
-- `meteo.wind_samples` est né sans clé naturelle : rejouer une extraction y
-- aurait dupliqué chaque échantillon, et un panache calculé ensuite aurait
-- compté deux fois le même vent. Le même point du même run à la même échéance
-- et au même niveau est une seule vérité — l'index l'impose, et l'écriture
-- (`store_samples`) devient un `on conflict do update` : rejouer rafraîchit.
--
-- L'égalité sur `location` est l'égalité binaire du type geometry : elle
-- convient parce que le point d'un événement est écrit à l'identique d'une
-- passe à l'autre — c'est une clé de rejeu, pas un rapprochement spatial.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

create unique index if not exists wind_samples_sample_key
  on meteo.wind_samples (model_run_id, level, valid_at, location);

comment on index meteo.wind_samples_sample_key is
  'Clé de rejeu : un échantillon par (run, niveau, échéance, point). Cahier §13.13.';
