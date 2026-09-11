-- =============================================================================
-- 20260911150000 — Heure attendue de la prochaine donnée (bandeau d'état)
--
-- Cahier v2.1 §8.1, FR-005 et FR-150.
--
-- Le bandeau d'état dit depuis quand la donnée date. Il lui manquait la
-- question suivante, que tout lecteur se pose devant une carte qui vieillit :
-- **et la prochaine ?**
--
-- La réponse ne s'invente pas. Le registre déclare déjà, pour chaque source,
-- l'`expected_interval` qui porte « sur l'âge de la **donnée**, pas sur la
-- cadence d'interrogation » (seed du registre) : pour FIRMS, c'est la période
-- de revisite des satellites polaires, pas le rythme des dix minutes de la
-- tâche. La même valeur sert déjà à qualifier une source de `delayed` — c'est
-- donc la borne que le service s'engage à tenir, et non une prédiction
-- orbitale que MapFeux ne sait pas faire.
--
-- La colonne est calculée **en base** plutôt que reconstituée côté web : un
-- `interval` traverse PostgREST sous plusieurs formes selon la version, et
-- une heure attendue vaut mieux qu'une soustraction refaite ailleurs.
--
-- `create or replace view` n'autorise que l'ajout de colonnes **en fin** de
-- liste : l'ordre existant est donc reproduit à l'identique.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

create or replace view api.source_status as
with last_success as (
  select
    r.source_id,
    max(r.finished_at) as finished_at,
    -- Agrégat et non « dernière valeur » : une tâche revenue vide ne doit pas
    -- effacer la fraîcheur apportée par ses voisines.
    max(r.source_data_at) as source_data_at
  from ingest.import_runs r
  where r.status in ('success', 'partial')
  group by r.source_id
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
    -- L'ordre compte : une source arrêtée n'est pas jugée sur sa fraîcheur,
    -- qui ne voudrait rien dire.
    when s.status in ('disabled', 'paused') and ls.finished_at is null then 'upcoming'
    when s.status in ('disabled', 'paused') then 'maintenance'
    when ls.finished_at is null then 'unavailable'
    when now() - coalesce(ls.source_data_at, ls.finished_at) >= s.stale_after then 'stale'
    when now() - coalesce(ls.source_data_at, ls.finished_at) >= s.expected_interval then 'delayed'
    else 'fresh'
  end as freshness,
  oi.public_message as incident_message,
  oi.opened_at as incident_opened_at,
  -- Nul tant qu'aucune donnée n'est arrivée : sans point de départ, une
  -- échéance serait une invention. Une source arrêtée en porte une, sans
  -- conséquence — le front ne lit cette colonne que pour les sources en
  -- service (`isInService`).
  ls.source_data_at + s.expected_interval as next_data_expected_at
from ingest.data_sources s
left join last_success ls on ls.source_id = s.id
left join open_incident oi on oi.source_id = s.id;

comment on view api.source_status is
  'Alimente /statut et le bandeau d''état. La fraîcheur agrège toutes les tâches d''une source '
  '(FR-110). `upcoming` = arrêtée et jamais entrée en service ; `maintenance` = arrêtée après '
  'avoir fonctionné ; `unavailable` = active mais sans aucun import réussi (FR-150). '
  '`next_data_expected_at` est l''échéance déclarée au registre, jamais une prédiction orbitale.';
