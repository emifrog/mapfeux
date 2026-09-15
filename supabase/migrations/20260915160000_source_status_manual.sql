-- =============================================================================
-- 20260915160000 — L'import manuel est un état, pas un retard
--
-- Cahier v2.1 §5.13 (fausse assurance), FR-110, FR-150. Plan §15.
--
-- Deux sources du registre ne sont lues par aucune tâche planifiée : les
-- limites administratives de l'IGN (ADMIN EXPRESS COG, une édition par an,
-- importée à la main) et les surfaces brûlées EFFIS (chargées à la demande
-- lors d'un grand feu). Le 15 septembre 2026, `/statut` lisait IGN
-- « Retardée · aucune donnée » — un import unique d'août, attendu tous les
-- trente jours — et EFFIS « Maintenance » — `disabled` après avoir livré, ce
-- que la vue lit comme un arrêt. Aucune des deux n'est en retard ni arrêtée :
-- elles sont **manuelles**, et la vue n'avait pas de mot pour ça. Un état
-- muet ou approximatif est exactement ce que §5.13 proscrit — et le
-- compteur d'en-tête en descendait à « 7/8 » sans qu'aucune panne existe.
--
-- `settings->>'import_mode' = 'manual'` est le marqueur ; l'IGN le portait
-- déjà, EFFIS le reçoit ici. Une source manuelle qui a livré au moins une fois
-- lit `manual`, quel que soit son statut au registre et quel que soit l'âge de
-- sa donnée — c'est la définition. Elle n'a pas de prochaine donnée attendue :
-- promettre une échéance à un geste humain serait l'inventer. Une source
-- manuelle qui n'a jamais livré reste `upcoming` ou `unavailable`, comme les
-- autres : l'état manuel décrit une lecture, pas une intention.
--
-- Le front porte le libellé « Import manuel » (paquet `ui`) et compte cette
-- source parmi celles en service et saines (`isHealthy`, paquet `domain`).
-- Idempotente : `create or replace view`, et un `update` sans effet au rejeu.
-- =============================================================================

update ingest.data_sources
set settings = coalesce(settings, '{}'::jsonb) || '{"import_mode": "manual"}'::jsonb,
    updated_at = now()
where key = 'effis'
  and coalesce(settings->>'import_mode', '') <> 'manual';

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
    -- L'import manuel d'abord : une source lue à la main n'est jugée ni sur
    -- son statut au registre ni sur l'âge de sa donnée — dès lors qu'elle a
    -- livré une fois.
    when s.settings->>'import_mode' = 'manual' and ls.finished_at is not null then 'manual'
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
  -- échéance serait une invention. Nul aussi pour un import manuel : un geste
  -- humain n'a pas d'échéance à promettre.
  case
    when s.settings->>'import_mode' = 'manual' then null
    else ls.source_data_at + s.expected_interval
  end as next_data_expected_at
from ingest.data_sources s
left join last_success ls on ls.source_id = s.id
left join open_incident oi on oi.source_id = s.id;

comment on view api.source_status is
  'Alimente /statut et le bandeau d''état. La fraîcheur agrège toutes les tâches d''une source '
  '(FR-110). `manual` = lue à la main, a livré au moins une fois, sans échéance ; `upcoming` = '
  'arrêtée et jamais entrée en service ; `maintenance` = arrêtée après avoir fonctionné ; '
  '`unavailable` = active mais sans aucun import réussi (FR-150). `next_data_expected_at` est '
  'l''échéance déclarée au registre, jamais une prédiction orbitale.';

notify pgrst, 'reload schema';
