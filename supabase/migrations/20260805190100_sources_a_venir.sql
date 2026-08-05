-- =============================================================================
-- 20260805190100 — Sources jamais mises en service : « à venir »
--
-- Cahier FR-150 et §5.13.
--
-- Le registre des sources a été écrit d'après le cahier, donc en avance sur ce
-- qui est implémenté. CAMS et le radar y figurent depuis l'origine ; leur
-- connecteur n'existe pas, et les schémas `air` et `radar` sont vides.
--
-- La vue les classait donc en `unavailable`, dont la définition est « aucun
-- import réussi ». C'est exact et trompeur à la fois : le mot annonce une
-- panne, là où il s'agit d'une fonctionnalité non encore construite. En façade,
-- cela donnait « 1 source sur 6 » sur toutes les pages — un service qui se
-- déclare cassé à 83 % alors qu'il est inachevé.
--
-- D'où une distinction sur ce qui les sépare réellement :
--
--   upcoming     arrêtée **et** jamais entrée en service
--   maintenance  arrêtée après avoir fonctionné
--
-- Les deux se lisent sur les mêmes colonnes, sans champ nouveau : `status` dit
-- l'intention, `finished_at` dit l'histoire.
--
-- Ce qui ne change pas : /statut continue de lister les six sources. On
-- qualifie, on ne masque pas (FR-150).
-- =============================================================================

-- Rattrapage des bases déjà ensemencées.
--
-- Sur une base vierge cet `update` ne touche rien : les migrations s'appliquent
-- avant le seed, et le registre est encore vide. C'est le seed qui y pose
-- désormais `disabled`, et c'est là que vit la vérité du registre. Cette ligne
-- ne sert qu'aux bases où le seed a tourné avec les valeurs antérieures — dont
-- le projet hébergé.
update ingest.data_sources
set status = 'disabled'
where key in ('cams', 'radar');

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
  oi.opened_at as incident_opened_at
from ingest.data_sources s
left join last_success ls on ls.source_id = s.id
left join open_incident oi on oi.source_id = s.id;

comment on view api.source_status is
  'Alimente /statut. La fraîcheur agrège toutes les tâches d''une source (FR-110). '
  '`upcoming` = arrêtée et jamais entrée en service ; `maintenance` = arrêtée après avoir '
  'fonctionné ; `unavailable` = active mais sans aucun import réussi (FR-150).';
