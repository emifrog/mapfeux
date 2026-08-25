-- =============================================================================
-- 20260825210000 — Surface publique des périmètres (jalon J9)
--
-- Cahier v2.1 FR-091 à FR-094. La fiche et la relecture lisent ici : toutes
-- les versions publiques, avec ce qui permet de les juger — nature, source
-- et attribution, validité, publication, surface **et sa méthode**,
-- résolution, confiance — et ce qui permet de les ordonner : la version
-- courante est celle qu'aucune version publique ne remplace.
--
-- Un périmètre masqué (FR-096) n'existe pas pour le public ; s'il remplaçait
-- une version, celle-ci redevient courante — le masquage d'une erreur ne
-- doit pas laisser la fiche sans rien quand une version antérieure valait.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

create or replace function api.fire_event_perimeters(event_public_id text)
returns table (
  id uuid,
  perimeter_type fire.perimeter_type,
  valid_at timestamptz,
  published_at timestamptz,
  imported_at timestamptz,
  area_ha numeric,
  source_area_ha numeric,
  resolution_m numeric,
  confidence_level fire.perimeter_confidence,
  method text,
  source_name text,
  source_attribution text,
  is_current boolean,
  supersedes_id uuid,
  geometry jsonb
)
language sql
stable
security definer
set search_path = fire, ingest, extensions, pg_temp
as $$
  select
    p.id,
    p.perimeter_type,
    p.valid_at,
    p.published_at,
    p.imported_at,
    p.area_ha,
    p.source_area_ha,
    p.resolution_m,
    p.confidence_level,
    p.method,
    s.name,
    s.attribution,
    not exists (
      select 1 from fire.event_perimeters n
      where n.supersedes_id = p.id and n.is_public
    ) as is_current,
    p.supersedes_id,
    extensions.st_asgeojson(p.geometry)::jsonb
  from fire.event_perimeters p
  join fire.events e on e.id = p.event_id
  join ingest.data_sources s on s.id = p.source_id
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and p.is_public
  order by p.valid_at desc, p.imported_at desc;
$$;

comment on function api.fire_event_perimeters(text) is
  'Versions publiques des périmètres d''un événement, source et méthode comprises. Cahier FR-091 à FR-094.';

grant execute on function api.fire_event_perimeters(text) to anon, authenticated;
