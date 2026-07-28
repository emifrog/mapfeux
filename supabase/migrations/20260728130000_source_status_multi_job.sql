-- =============================================================================
-- 20260728130000 — Fraîcheur d'une source alimentée par plusieurs tâches
--
-- Cahier §5.13 et FR-110.
--
-- Défaut constaté en exploitation. FIRMS est importé par quatre tâches, une par
-- produit satellitaire. La vue retenait le dernier import **terminé** et sa date
-- de donnée. Or le dernier terminé est MODIS, qui ne rapporte souvent rien sur
-- une petite emprise : sa date de donnée est nulle, et `/statut` affichait donc
-- « aucune donnée » alors que trois jeux VIIRS venaient d'être importés avec
-- succès quelques secondes plus tôt.
--
-- La date de donnée d'une source est désormais la plus récente **toutes tâches
-- confondues**, ce qui est la question réellement posée : « à quand remonte la
-- donnée la plus fraîche dont nous disposons pour cette source ». Idem pour la
-- date du dernier import réussi.
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
    when s.status = 'disabled' then 'maintenance'
    when s.status = 'paused' then 'maintenance'
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
  'Alimente /statut. La fraîcheur agrège toutes les tâches d''une source : une tâche revenue vide n''efface pas la donnée apportée par les autres (FR-110).';
