-- =============================================================================
-- 20260809120000 — Catalogue national des événements, paginé par curseur
--
-- Cahier v2.1 FR-050 à FR-055 et §15.4 ; J7 « expérience FeuScope ».
--
-- Le catalogue liste sans emprise : c'est la vue nationale, bornée par une
-- pagination par jeu de clés — (last_detected_at, id) strictement décroissant —
-- jamais par un offset qui se paie sur les tables volumineuses (§15.1).
--
-- Le tri est la dernière observation (FR-052) : aucun classement par
-- « importance », qu'aucune règle sourcée ne définit (FR-055).
--
-- Les deux bornes du curseur voyagent ensemble : l'une sans l'autre est
-- ignorée plutôt qu'interprétée — un curseur tronqué ne doit pas inventer une
-- page. Le jeu de clés s'appuie sur `public_id`, jamais sur l'identifiant
-- interne : un curseur se décode, et il ne doit rien divulguer (§15.1).
-- =============================================================================

-- Première forme, brièvement déployée avec l'identifiant interne en curseur.
drop function if exists
  api.events_catalog(timestamptz, timestamptz, text, text, timestamptz, uuid, integer);

create or replace function api.events_catalog(
  since timestamptz default null,
  until_at timestamptz default null,
  department text default null,
  verification text default null,
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
      cursor_last is null or cursor_public is null
      or (e.last_detected_at, e.public_id) < (cursor_last, cursor_public)
    )
  order by e.last_detected_at desc, e.public_id desc
  limit least(greatest(coalesce(max_results, 50), 1), 100);
$$;

-- Commentaire qualifié par la signature : au rejeu, une autre surcharge peut
-- coexister le temps de la migration suivante, et un nom nu serait ambigu
-- (42725) — vécu le 9 août au db push.
comment on function
  api.events_catalog(timestamptz, timestamptz, text, text, timestamptz, text, integer) is
  'Catalogue national trié par dernière observation, pagination par jeu de '
  'clés sur (last_detected_at, public_id). FR-050 à FR-055.';

grant execute on function
  api.events_catalog(timestamptz, timestamptz, text, text, timestamptz, text, integer)
to anon, authenticated;
