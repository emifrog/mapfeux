-- =============================================================================
-- 20260915230000 — La recherche de commune passe par ses index
--
-- Trouvé le 15 septembre 2026 au soir, en vérifiant autre chose : la
-- recherche « nice » expirait en production. `api.search_municipalities`
-- testait le code postal par `q = any (m.postal_codes)`, une forme que
-- l'index GIN sur `postal_codes` ne sert pas ; dans un `or` avec les deux
-- prédicats trigramme, elle forçait un parcours séquentiel de la table
-- entière — 316 lignes au pilote, 34 746 depuis l'import national, avec
-- leurs géométries. Mesuré : 3,1 s à froid, 1,1 s à chaud, contre les 3 s
-- de `statement_timeout` du rôle `anon`, et la cible de 300 ms du §6.2.
--
-- `m.postal_codes @> array[q]` dit la même chose et se sert de l'index :
-- le planificateur combine alors les trois index en un `BitmapOr` —
-- 283 ms à froid, 40 à 150 ms à chaud sur les mêmes requêtes. Même
-- signature, `create or replace` : idempotente et rejouable.
-- =============================================================================

create or replace function api.search_municipalities(q text, max_results integer default 10)
returns table (
  insee_code text,
  name text,
  department_code text,
  postal_codes text[],
  longitude double precision,
  latitude double precision
)
language sql
stable
security definer
set search_path = geo, extensions, pg_temp
as $$
  with needle as (
    select geo.normalize_name(coalesce(q, '')) as value
  )
  select
    m.insee_code,
    m.name,
    m.department_code,
    m.postal_codes,
    extensions.st_x(m.centroid),
    extensions.st_y(m.centroid)
  from geo.municipalities m, needle n
  where m.valid_to is null
    and length(n.value) >= 1
    and (
      m.normalized_name like n.value || '%'
      or m.normalized_name % n.value
      -- `@>` et non `= any (...)` : seule cette forme est servie par l'index
      -- GIN sur les codes postaux, et sans elle tout le `or` retombe en
      -- parcours séquentiel.
      or m.postal_codes @> array[q]
    )
  order by
    (m.normalized_name = n.value) desc,
    (m.normalized_name like n.value || '%') desc,
    extensions.similarity(m.normalized_name, n.value) desc,
    m.name
  limit least(greatest(coalesce(max_results, 10), 1), 25);
$$;

comment on function api.search_municipalities is
  'Recherche tolérante par nom ou code postal, code INSEE comme identifiant de '
  'référence (FR-020). Les trois prédicats passent par leurs index : le code '
  'postal par `@>`, jamais par `= any` (52ᵉ migration).';

grant execute on function api.search_municipalities(text, integer) to anon, authenticated;
