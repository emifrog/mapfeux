-- =============================================================================
-- 20260915143000 — Les agrégats départementaux portent nom et destination
--
-- Cahier v2.1 §21.3, FR-003, FR-014.
--
-- `/carte` s'ouvre désormais sur la France et lit, sous le zoom 7, la liste
-- des départements concernés. Cette liste nommait les départements par le
-- registre public des territoires — qui ne publie que les territoires
-- `pilot` et `active` (FR-014) : quatre-vingts départements touchés sur les
-- sept derniers jours s'affichaient donc sous leur code, et aucun ne pouvait
-- mener la carte sur lui. Constaté le 15 septembre 2026.
--
-- La fonction d'agrégats joint déjà `app.territories`, qui connaît le nom, le
-- centre et le zoom par défaut de tous les départements, brouillons compris :
-- elle les rend. Publier le nom et le centre d'un département « à venir »
-- n'est pas publier son territoire — il n'a toujours ni page ni liens, et son
-- statut le dit dans la même ligne.
--
-- Le type de retour change : Postgres refuse de le modifier en place, la
-- fonction est donc supprimée puis recréée. Idempotente par construction —
-- `drop function if exists`, puis `create` — et rejouable.
-- =============================================================================

drop function if exists api.department_event_aggregates(timestamptz);

create function api.department_event_aggregates(since timestamptz default null)
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
  'Compte des événements visibles par département, avec le nom et le centre du '
  'département pour que la carte nationale puisse le nommer et s''y rendre. Un '
  'département absent du résultat n''a aucun événement sur la période. FR-003.';

grant execute on function api.department_event_aggregates(timestamptz) to anon, authenticated;

-- PostgREST recharge son cache de schéma sur ce signal ; Supabase le fait aussi
-- par déclencheur d'événement, mais deux fois ne coûte rien.
notify pgrst, 'reload schema';
