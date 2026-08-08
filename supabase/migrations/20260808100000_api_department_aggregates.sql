-- =============================================================================
-- 20260808100000 — Agrégats d'événements par département
--
-- Cahier v2.1 FR-003, §21.2 et §21.3 ; J3 « agrégation par département ».
--
-- Aux faibles niveaux de zoom, la carte ne charge ni géométries communales ni
-- événements individuels : un compte par département suffit, posé sur les
-- polygones déjà servis en tuiles vectorielles.
--
-- L'agrégat compte depuis la vue `api.fire_events` — la même que la carte —
-- et non depuis les tables : ce que la vue masque, l'agrégat l'ignore par
-- construction, aujourd'hui comme après tout durcissement de la vue.
--
-- Le rattachement au département est spatial (territoires importés le
-- 7 août), avec repli sur le préfixe INSEE de la commune la plus proche : un
-- point littoral peut tomber hors du polygone simplifié à ~100 m, et une
-- détection comptée nulle part serait une détection dissimulée (§17.7).
-- =============================================================================

create or replace function api.department_event_aggregates(since timestamptz default null)
returns table (
  department_code text,
  department_slug text,
  department_status text,
  events integer,
  substantiated integer,
  last_detected_at timestamptz
)
language sql
stable
security definer
set search_path = api, fire, app, extensions, pg_temp
as $$
  with visible as (
    select
      v.confidence_level,
      e.last_detected_at,
      e.representative_point,
      e.nearest_municipality_code
    from api.fire_events v
    join fire.events e on e.id = v.id
    where (since is null or e.last_detected_at >= since)
  ),
  assigned as (
    select
      coalesce(
        (
          select d.code
          from app.territories d
          where d.type = 'department'
            and d.geometry is not null
            and extensions.st_intersects(d.geometry, visible.representative_point)
          limit 1
        ),
        upper(left(visible.nearest_municipality_code, 2))
      ) as code,
      visible.confidence_level,
      visible.last_detected_at
    from visible
  )
  select
    d.code,
    d.slug,
    d.status::text,
    count(*)::integer,
    -- « Étayé » : la définition de la carte et de la liste (confiance moyenne
    -- ou élevée), jamais une seconde convention.
    count(*) filter (where a.confidence_level in ('medium', 'high'))::integer,
    max(a.last_detected_at)
  from assigned a
  join app.territories d on d.type = 'department' and d.code = a.code
  group by d.code, d.slug, d.status;
$$;

comment on function api.department_event_aggregates is
  'Compte des événements visibles par département. Un département absent du '
  'résultat n''a aucun événement sur la période. FR-003.';

grant execute on function api.department_event_aggregates(timestamptz) to anon, authenticated;
