-- =============================================================================
-- 20260915220000 — L'état reconstitué se calcule en base, jamais sur une liste tronquée
--
-- Constat 3 de l'audit externe du 15 septembre 2026 (plan §15). La route
-- `/state?at=` et la relecture lisaient les 2 000 observations **les plus
-- récentes** de l'événement, puis filtraient `at` en mémoire : avec 2 001
-- observations, l'état à l'instant de la première rendait zéro observation et
-- `effectiveAt` nul, et les comptes comme les maxima étaient sous-estimés.
-- Latent — 1 033 observations au plus en production ce jour-là —, mais un
-- plafond qui tronque l'histoire en silence n'est pas un plafond, c'est un
-- mensonge en attente (§21.5).
--
-- Trois choses :
--
-- 1. `api.fire_event_detections` prend un `until_at` : les observations
--    servies sont celles **à l'instant demandé**, les plus récentes d'abord,
--    et le plafond de 2 000 mord sur cet ensemble, pas sur toute la vie de
--    l'événement. L'ancienne signature `(text, integer)` est supprimée : deux
--    surcharges aux mêmes paramètres nommés seraient ambiguës pour PostgREST
--    (la leçon du 9 août, plan §15).
-- 2. `api.fire_event_state` calcule les agrégats d'un instant **en base et
--    sans plafond** : compte, dernière observation effective, capteurs, FRP
--    maximale. Ce que la liste ne peut pas garantir, la base le garantit.
-- 3. `api.fire_event_observation_times` donne les instants d'acquisition
--    distincts — les pas de la relecture (FR-080) —, sans plafond : quelques
--    centaines de lignes au plus, là où les observations se comptent en
--    milliers.
--
-- Rejouable : `drop function if exists` puis `create or replace`, droits
-- reposés.
-- =============================================================================

drop function if exists api.fire_event_detections(text, integer);

create or replace function api.fire_event_detections(
  event_public_id text,
  max_results integer default 500,
  until_at timestamptz default null
)
returns table (
  acquired_at timestamptz,
  sensor text,
  satellite text,
  longitude double precision,
  latitude double precision,
  confidence_level text,
  frp_mw numeric,
  day_night char(1),
  is_known_thermal_source boolean
)
language sql
stable
security definer
set search_path = fire, extensions, pg_temp
as $$
  select
    d.acquired_at,
    d.sensor,
    d.satellite,
    extensions.st_x(d.location),
    extensions.st_y(d.location),
    -- La confiance fournisseur brute n'est pas publiée telle quelle : elle
    -- n'a pas le même sens entre VIIRS et MODIS. Seul le niveau normalisé
    -- sort, et « inconnu » reste « inconnu » (§17.3).
    case
      when d.confidence_score is null then 'unknown'
      when d.confidence_score >= 0.8 then 'high'
      when d.confidence_score >= 0.5 then 'medium'
      else 'low'
    end,
    d.frp_mw,
    d.day_night,
    d.known_source_id is not null
  from fire.event_detections ed
  join fire.events e on e.id = ed.event_id
  join fire.detections d
    on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and d.is_public
    and (until_at is null or d.acquired_at <= until_at)
  order by d.acquired_at desc
  limit least(greatest(coalesce(max_results, 500), 1), 2000);
$$;

comment on function api.fire_event_detections(text, integer, timestamptz) is
  'Détections membres d''un événement, les plus récentes d''abord, à un instant '
  'donné (`until_at`, sinon toutes). Plafond 2 000 sur cet ensemble : au-delà, '
  'l''appelant l''annonce et lit les comptes dans api.fire_event_state. '
  'raw_payload n''est jamais exposé (ADR-004).';

create or replace function api.fire_event_state(
  event_public_id text,
  until_at timestamptz
)
returns table (
  observation_count bigint,
  effective_at timestamptz,
  sensors text[],
  frp_max_mw numeric
)
language sql
stable
security definer
set search_path = fire, extensions, pg_temp
as $$
  select
    count(*),
    max(d.acquired_at),
    coalesce(
      array_agg(distinct d.sensor order by d.sensor) filter (where d.sensor is not null),
      '{}'::text[]
    ),
    max(d.frp_mw)
  from fire.event_detections ed
  join fire.events e on e.id = ed.event_id
  join fire.detections d
    on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and d.is_public
    and d.acquired_at <= until_at;
$$;

comment on function api.fire_event_state(text, timestamptz) is
  'L''état d''un événement à un instant : compte, dernière observation '
  'effective, capteurs et FRP maximale sur **toutes** les observations '
  'publiques jusqu''à cet instant — sans plafond, contrairement à la liste '
  '(FR-084, FR-086). Une ligne, à zéro si rien n''était observé.';

create or replace function api.fire_event_observation_times(event_public_id text)
returns table (
  acquired_at timestamptz,
  observation_count bigint
)
language sql
stable
security definer
set search_path = fire, extensions, pg_temp
as $$
  select d.acquired_at, count(*)
  from fire.event_detections ed
  join fire.events e on e.id = ed.event_id
  join fire.detections d
    on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and d.is_public
  group by d.acquired_at
  order by d.acquired_at;
$$;

comment on function api.fire_event_observation_times(text) is
  'Les instants d''acquisition distincts d''un événement, du plus ancien au '
  'plus récent, avec le nombre d''observations de chacun — les pas de la '
  'relecture (FR-080). Sans plafond : quelques centaines de lignes au plus.';

grant execute on function
  api.fire_event_detections(text, integer, timestamptz),
  api.fire_event_state(text, timestamptz),
  api.fire_event_observation_times(text)
to anon, authenticated;
