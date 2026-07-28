-- =============================================================================
-- 20260728100000 — Fraîcheur des sources : ne pas confondre « donnée sans date »
-- et « source indisponible »
--
-- Cahier §5.13 et annexe D.
--
-- Défaut constaté en exploitation : après deux imports IGN réussis,
-- `api.source_status` classait la source en `unavailable`. La vue calculait la
-- fraîcheur sur `source_data_at` seul, or certaines sources ne publient pas la
-- date de leurs propres données — l'API Découpage administratif n'expose aucun
-- millésime COG (ADR-017). Un import réussi laissait donc la colonne nulle, et
-- la source apparaissait en panne.
--
-- `unavailable` signifie désormais ce qu'il doit signifier : aucun import n'a
-- jamais réussi. Lorsque la date de la donnée est inconnue, la fraîcheur se
-- calcule sur l'heure du dernier import réussi, qui en est le majorant le plus
-- proche. `last_data_at` reste nul, de sorte que l'interface puisse distinguer
-- une date connue d'une date inférée.
-- =============================================================================

create or replace view api.source_status as
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
  -- Date des données elles-mêmes. Reste nulle si la source ne la publie pas :
  -- l'interface doit pouvoir dire « date inconnue » plutôt que d'inventer.
  ls.source_data_at as last_data_at,
  case
    when s.status = 'disabled' then 'maintenance'
    when s.status = 'paused' then 'maintenance'
    -- Aucun import réussi : c'est le seul cas d'indisponibilité.
    when ls.finished_at is null then 'unavailable'
    when now() - coalesce(ls.source_data_at, ls.finished_at) >= s.stale_after then 'stale'
    when now() - coalesce(ls.source_data_at, ls.finished_at) >= s.expected_interval then 'delayed'
    else 'fresh'
  end as freshness,
  oi.public_message as incident_message,
  oi.opened_at as incident_opened_at
from ingest.data_sources s
left join last_success ls on ls.source_id = s.id
left join open_incident oi on oi.source_id = s.id;

comment on view api.source_status is
  'Alimente /statut. `unavailable` signifie « aucun import réussi », pas « date de donnée inconnue » (FR-110, FR-112).';
