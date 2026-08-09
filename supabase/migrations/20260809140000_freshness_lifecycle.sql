-- =============================================================================
-- 20260809140000 — Cycle de vie de la fraîcheur technique, version 1
--
-- Cahier v2.1 FR-048, §17.4 et annexe D ; J7.
--
-- Sans lui, tout événement restait « nouvel événement » pour toujours : 932
-- sur 933 en production le 9 août, dont des événements de quatre jours que la
-- fiche présentait comme « créés récemment ». La fraîcheur est une dimension
-- technique dérivée du temps : elle se recalcule, elle ne se fige pas.
--
-- Règles `cycle-de-vie-v1` :
--   new         créé il y a moins de 24 h ;
--   recent      dernière observation il y a moins de 48 h ;
--   not_recent  dernière observation il y a 48 h ou plus — sans conclusion
--               sur l'extinction (FR-048) ;
--   archived    dernière observation il y a 7 jours ou plus. Terminal pour
--               l'automate : le regroupement n'attache plus à un événement
--               archivé, une reprise crée un événement neuf.
--
-- `hidden` est une décision administrative : l'automate ne le lit ni ne
-- l'écrit (§17.5). Les statuts officiels ne sont jamais touchés — la
-- fraîcheur satellitaire et le statut officiel coexistent (§17.4).
-- =============================================================================

-- Première forme, brièvement déployée : rendait un compte. La chaîne a besoin
-- des identifiants pour reconstruire les snapshots des requalifiés — et les
-- règles ne doivent vivre qu'ici, jamais recopiées dans un appelant.
drop function if exists fire.refresh_freshness();

create or replace function fire.refresh_freshness()
returns setof uuid
language sql
volatile
set search_path = fire, pg_temp
as $$
  with target as (
    select
      e.id,
      case
        when e.last_detected_at <= now() - interval '7 days' then 'archived'
        when e.last_detected_at <= now() - interval '48 hours' then 'not_recent'
        when e.created_at > now() - interval '24 hours' then 'new'
        else 'recent'
      end::fire.freshness_status as status
    from fire.events e
    where e.freshness_status not in ('hidden', 'archived')
  )
  update fire.events e
  set freshness_status = target.status
  from target
  where target.id = e.id
    and e.freshness_status <> target.status
  returning e.id;
$$;

comment on function fire.refresh_freshness is
  'Recalcule la fraîcheur technique (cycle-de-vie-v1) et rend les '
  'identifiants requalifiés. FR-048 ; ne touche ni hidden ni archived.';

grant execute on function fire.refresh_freshness() to mapfeux_ingest;

-- =============================================================================
-- Le catalogue apprend la fraîcheur : /archives est un filtre, pas une table.
-- L'ancienne signature est retirée — deux surcharges du même nom rendraient
-- l'appel PostgREST ambigu.
-- =============================================================================

drop function if exists
  api.events_catalog(timestamptz, timestamptz, text, text, timestamptz, text, integer);

create or replace function api.events_catalog(
  since timestamptz default null,
  until_at timestamptz default null,
  department text default null,
  verification text default null,
  freshness text default null,
  cursor_last timestamptz default null,
  cursor_public text default null,
  max_results integer default 50
)
returns setof api.fire_events
language sql
stable
security definer
set search_path = api, fire, extensions, pg_temp
as $$
  select v.*
  from api.fire_events v
  join fire.events e on e.id = v.id
  where (since is null or e.last_detected_at >= since)
    and (until_at is null or e.last_detected_at < until_at)
    and (
      department is null
      or upper(left(e.nearest_municipality_code, 2)) = upper(department)
    )
    and (
      verification is null
      or e.verification_status = verification::fire.verification_status
    )
    and (
      freshness is null
      or e.freshness_status = freshness::fire.freshness_status
    )
    and (
      cursor_last is null or cursor_public is null
      or (e.last_detected_at, e.public_id) < (cursor_last, cursor_public)
    )
  order by e.last_detected_at desc, e.public_id desc
  limit least(greatest(coalesce(max_results, 50), 1), 100);
$$;

comment on function
  api.events_catalog(timestamptz, timestamptz, text, text, text, timestamptz, text, integer) is
  'Catalogue national trié par dernière observation, pagination par jeu de '
  'clés sur (last_detected_at, public_id). FR-050 à FR-055.';

grant execute on function
  api.events_catalog(timestamptz, timestamptz, text, text, text, timestamptz, text, integer)
to anon, authenticated;
