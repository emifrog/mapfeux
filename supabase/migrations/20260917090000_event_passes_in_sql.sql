-- =============================================================================
-- 20260917090000 — Les passages satellitaires d'un événement se calculent en base
--
-- Plan §15, reste du constat 3 de l'audit du 15 septembre 2026 : le
-- graphique de puissance radiative par passage de la fiche était calculé
-- en TypeScript sur les 500 observations les plus récentes — le plafond du
-- tableau —, et un événement plus grand voyait ses premiers passages
-- disparaître du graphique, avec une phrase pour le dire. La phrase était
-- honnête ; le graphique restait faux par omission.
--
-- La règle est celle de `lib/events/passes.ts`, reproduite ici : un passage
-- est l'ensemble des pixels **du même satellite** acquis à moins de dix
-- minutes **du premier pixel du passage** — pas du précédent : un passage
-- dure des secondes, et un satellite ne revient pas avant une centaine de
-- minutes. Les pixels d'une même minute sont d'abord fondus, puis les
-- minutes sont chaînées par une récursion : quelques dizaines de lignes par
-- satellite, là où les pixels se comptent en centaines.
--
-- La puissance d'un passage est la somme des puissances connues, arrondie
-- au dixième ; un passage sans aucune puissance connue reste un passage,
-- sans puissance (FR-053). Jour ou nuit à la majorité des pixels, le jour
-- l'emportant à égalité — comme en TypeScript. Le capteur est celui du
-- premier pixel.
--
-- Sans plafond : tous les passages, du premier au dernier. Rejouable :
-- `create or replace`, droits reposés.
-- =============================================================================

create or replace function api.fire_event_passes(event_public_id text)
returns table (
  pass_at timestamptz,
  satellite text,
  sensor text,
  pixels bigint,
  frp_total_mw numeric,
  frp_max_mw numeric,
  day_night char(1)
)
language sql
stable
security definer
set search_path = fire, extensions, pg_temp
as $$
  with recursive pixels as (
    select d.acquired_at, d.satellite, d.sensor, d.frp_mw, d.day_night
    from fire.event_detections ed
    join fire.events e on e.id = ed.event_id
    join fire.detections d
      on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
    where e.public_id = event_public_id
      and e.freshness_status <> 'hidden'
      and d.is_public
  ),
  minutes as (
    select satellite, acquired_at,
           row_number() over (partition by satellite order by acquired_at) as rn
    from (select distinct satellite, acquired_at from pixels) m
  ),
  islands (satellite, acquired_at, rn, pass_at) as (
    select satellite, acquired_at, rn, acquired_at
    from minutes
    where rn = 1
    union all
    select m.satellite, m.acquired_at, m.rn,
           case
             when m.acquired_at - i.pass_at <= interval '10 minutes' then i.pass_at
             else m.acquired_at
           end
    from islands i
    join minutes m on m.satellite = i.satellite and m.rn = i.rn + 1
  )
  select
    i.pass_at,
    i.satellite,
    (array_agg(p.sensor order by p.acquired_at))[1],
    count(*),
    round(sum(p.frp_mw), 1),
    max(p.frp_mw),
    case
      when count(*) filter (where p.day_night in ('D', 'N')) = 0 then null
      when count(*) filter (where p.day_night = 'D')
           >= count(*) filter (where p.day_night = 'N') then 'D'
      else 'N'
    end
  from islands i
  join pixels p on p.satellite = i.satellite and p.acquired_at = i.acquired_at
  group by i.pass_at, i.satellite
  order by i.pass_at, i.satellite;
$$;

comment on function api.fire_event_passes(text) is
  'Les passages satellitaires d''un événement, du premier au dernier, sans '
  'plafond : même satellite, pixels à moins de dix minutes du premier pixel '
  'du passage (la règle de lib/events/passes.ts). Puissance = somme des '
  'puissances connues, arrondie au dixième — une déduction (FR-053).';

grant execute on function api.fire_event_passes(text) to anon, authenticated;
