-- =============================================================================
-- 20260915150000 — Un département ne compte que ce qui est chez lui
--
-- Cahier v2.1 §2.4, §21.3, FR-003.
--
-- Trouvé le 15 septembre 2026 en ouvrant `/carte` sur la France : les
-- Pyrénées-Atlantiques annonçaient 80 événements sur sept jours, dont 7
-- seulement dans le polygone du département. Les 73 autres lui étaient
-- attribués par le repli « préfixe de la commune la plus proche » — des
-- points entre 41,0° et 43,6° de latitude, jusqu'à 5,7° ouest : le golfe de
-- Gascogne et le nord de l'Espagne, dont la commune française la plus proche
-- est Hendaye. La zone d'import FIRMS est un rectangle qui déborde des
-- frontières ; le repli faisait de chaque département frontalier le comptable
-- du pays voisin, et de l'accueil — « événements observés, France entière » —
-- une somme qui comptait l'Espagne et la Belgique : 716 sur sept jours, dont
-- 322 en France.
--
-- Le repli n'était pas gratuit : un feu de littoral peut avoir son point
-- représentatif en mer, hors de tout polygone. Il est donc borné à ce qu'il
-- devait couvrir — le département **le plus proche à moins de 0,05 degré**,
-- cinq kilomètres environ, en géométrie plane : la version sphéroïdale
-- dépassait le délai de huit secondes du rôle `anon` et l'accueil lisait
-- zéro. Au-delà, l'événement n'est compté dans aucun département, et n'entre
-- plus dans le total national. Il reste visible sur la carte à l'échelle
-- d'une zone et dans le catalogue : ce que fait l'ingestion des détections
-- hors de France est une décision à part (plan §15).
--
-- Même signature : `create or replace` suffit, idempotent et rejouable.
-- =============================================================================

create or replace function api.department_event_aggregates(since timestamptz default null)
returns table (
  department_code text,
  department_slug text,
  department_status text,
  department_name text,
  center_longitude double precision,
  center_latitude double precision,
  default_zoom numeric,
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
      e.representative_point
    from api.fire_events v
    join fire.events e on e.id = v.id
    where (since is null or e.last_detected_at >= since)
  ),
  assigned as (
    select
      d.code,
      visible.confidence_level,
      visible.last_detected_at
    from visible
    -- Une seule recherche par événement : le département qui le contient
    -- d'abord, sinon le plus proche à moins de 0,05° — le littoral —, sinon
    -- aucun.
    join lateral (
      select t.code
      from app.territories t
      where t.type = 'department'
        and t.geometry is not null
        and extensions.st_dwithin(t.geometry, visible.representative_point, 0.05)
      order by
        extensions.st_intersects(t.geometry, visible.representative_point) desc,
        extensions.st_distance(t.geometry, visible.representative_point)
      limit 1
    ) d on true
  )
  select
    d.code,
    d.slug,
    d.status::text,
    d.name,
    extensions.st_x(d.center),
    extensions.st_y(d.center),
    d.default_zoom,
    count(*)::integer,
    -- « Étayé » : la définition de la carte et de la liste (confiance moyenne
    -- ou élevée), jamais une seconde convention.
    count(*) filter (where a.confidence_level in ('medium', 'high'))::integer,
    max(a.last_detected_at)
  from assigned a
  join app.territories d on d.type = 'department' and d.code = a.code
  group by d.code, d.slug, d.status, d.name, d.center, d.default_zoom;
$$;

comment on function api.department_event_aggregates(timestamptz) is
  'Compte des événements visibles par département — dans son polygone, ou en mer '
  'à moins de 0,05° —, avec le nom et le centre du département pour que la carte '
  'nationale puisse le nommer et s''y rendre. Un département absent du résultat '
  'n''a aucun événement sur la période ; un événement hors de France n''est compté '
  'nulle part. FR-003.';

grant execute on function api.department_event_aggregates(timestamptz) to anon, authenticated;

notify pgrst, 'reload schema';
