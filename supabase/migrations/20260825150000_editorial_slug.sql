-- =============================================================================
-- 20260825150000 — Slug éditorial facultatif des événements (jalon J7)
--
-- Cahier v2.1 FR-042 et FR-060 : chaque événement possède un identifiant
-- public opaque, un slug éditorial **facultatif** et une URL permanente
-- `/evenements/[publicId]/[slug?]`.
--
-- Le slug est un acte éditorial, jamais une génération : un slug automatique
-- écrirait « incendie » dans l'URL d'un regroupement algorithmique — la
-- formulation non sourcée que le §2.4 interdit, gravée là où elle ne se
-- corrige plus. La colonne naît nulle partout et le restera jusqu'à ce qu'un
-- humain nomme (l'interface arrive avec J5) ; l'URL nue reste permanente et
-- servie quoi qu'il arrive, le slug ne fait que s'y ajouter.
--
-- `api.fire_event` gagne une colonne : son type de retour change, ce qui
-- interdit `create or replace` — la fonction est supprimée puis recréée dans
-- la même transaction, et son droit d'exécution reposé. Idempotente (dette
-- « migrations hors bande », plan §15) ; références qualifiées par signature.
-- =============================================================================

alter table fire.events
  add column if not exists editorial_slug text;

-- Drop puis add : le rejeu converge vers la définition courante, là où un
-- simple garde `duplicate_object` figerait la première version posée.
alter table fire.events
  drop constraint if exists events_editorial_slug_format;

alter table fire.events
  add constraint events_editorial_slug_format
  check (
    editorial_slug is null
    or (
      editorial_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
      and length(editorial_slug) <= 80
      -- Les segments réservés sous /evenements/[publicId]/ : un slug qui les
      -- porterait serait inatteignable, le routeur faisant primer le statique.
      and editorial_slug not in ('relecture', 'opengraph-image')
    )
  );

comment on column fire.events.editorial_slug is
  'Slug éditorial facultatif (FR-042). Posé par un humain, jamais généré : un slug porte des mots, et les mots suivent le vocabulaire public (§2.4).';

-- =============================================================================
-- api.fire_event — recréée avec la colonne
-- =============================================================================

drop function if exists api.fire_event(text);

create function api.fire_event(event_public_id text)
returns table (
  public_id text,
  freshness_status fire.freshness_status,
  verification_status fire.verification_status,
  official_control_status fire.official_control_status,
  official_status_at timestamptz,
  official_organisation text,
  official_source_url text,
  first_detected_at timestamptz,
  last_detected_at timestamptz,
  longitude double precision,
  latitude double precision,
  detection_count integer,
  sensor_count integer,
  sensors text[],
  satellites text[],
  confidence_level app.confidence_level,
  frp_min_mw numeric,
  frp_median_mw numeric,
  frp_max_mw numeric,
  nearest_municipality_code text,
  nearest_municipality_name text,
  territory_slug text,
  territory_name text,
  territory_timezone text,
  last_public_snapshot_at timestamptz,
  updated_at timestamptz,
  timeline_entry_count integer,
  timeline_latest_at timestamptz,
  editorial_slug text
)
language sql
stable
security definer
set search_path = fire, app, geo, extensions, pg_temp
as $$
  select
    e.public_id,
    e.freshness_status,
    e.verification_status,
    e.official_control_status,
    e.official_status_at,
    om.organisation,
    om.source_url,
    e.first_detected_at,
    e.last_detected_at,
    extensions.st_x(e.representative_point),
    extensions.st_y(e.representative_point),
    e.detection_count,
    e.sensor_count,
    coalesce(members.sensors, '{}'),
    coalesce(members.satellites, '{}'),
    e.confidence_level,
    e.frp_min_mw,
    e.frp_median_mw,
    e.frp_max_mw,
    e.nearest_municipality_code,
    m.name,
    t.slug,
    t.name,
    coalesce(t.timezone, 'Europe/Paris'),
    e.last_public_snapshot_at,
    e.updated_at,
    coalesce(tl.entry_count, 0)::integer,
    tl.latest_at,
    e.editorial_slug
  from fire.events e
  left join geo.municipalities m on m.insee_code = e.nearest_municipality_code
  left join app.territories t on t.id = e.territory_id
  left join app.official_messages om on om.id = e.official_status_source_id
  left join lateral (
    select
      array_agg(distinct d.sensor order by d.sensor) as sensors,
      array_agg(distinct d.satellite order by d.satellite) as satellites
    from fire.event_detections ed
    join fire.detections d
      on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
    where ed.event_id = e.id
      and d.is_public
  ) members on true
  left join lateral (
    select count(*) as entry_count, max(te.occurred_at) as latest_at
    from fire.event_timeline_entries te
    where te.event_id = e.id and te.visibility = 'public'
  ) tl on true
  where e.public_id = event_public_id
    -- Un événement masqué n'existe pas pour le public, y compris par son URL
    -- directe. Le masquage n'est pas une simple absence de la carte (§17.7).
    and e.freshness_status <> 'hidden';
$$;

comment on function api.fire_event(text) is
  'Fiche événement complète en une requête, slug éditorial compris. Cahier §5.6, FR-042.';

grant execute on function api.fire_event(text) to anon, authenticated;

-- =============================================================================
-- Snapshot : le slug entre dans l'état figé
--
-- Même type de retour, `create or replace` suffit. Les snapshots existants ne
-- portent pas la clé : le web lit `editorialSlug ?? null`, et chaque
-- reconstruction la pose.
-- =============================================================================

create or replace function fire.refresh_event_snapshot(target_event_id uuid)
returns timestamptz
language plpgsql
security definer
set search_path = fire, app, geo, extensions, pg_temp
as $$
declare
  v_payload jsonb;
  v_data_at timestamptz;
  v_public_id text;
  v_generated_at timestamptz := now();
begin
  select
    e.public_id,
    e.last_detected_at,
    jsonb_build_object(
      'id', e.public_id,
      'editorialSlug', e.editorial_slug,
      'freshnessStatus', e.freshness_status,
      'verificationStatus', e.verification_status,
      'officialControlStatus', e.official_control_status,
      'officialStatusSource',
        case
          when om.id is null then null
          else jsonb_build_object(
            'organisation', om.organisation,
            'url', om.source_url,
            'publishedAt', e.official_status_at
          )
        end,
      'firstDetectedAt', e.first_detected_at,
      'lastDetectedAt', e.last_detected_at,
      'location', jsonb_build_object(
        'longitude', extensions.st_x(e.representative_point),
        'latitude', extensions.st_y(e.representative_point)
      ),
      'detectionCount', e.detection_count,
      'sensorCount', e.sensor_count,
      'sensors', coalesce(to_jsonb(members.sensors), '[]'::jsonb),
      'satellites', coalesce(to_jsonb(members.satellites), '[]'::jsonb),
      'confidence', e.confidence_level,
      'frpMw', jsonb_build_object(
        'min', e.frp_min_mw, 'median', e.frp_median_mw, 'max', e.frp_max_mw
      ),
      'nearestMunicipality',
        case
          when m.insee_code is null then null
          else jsonb_build_object('insee', m.insee_code, 'name', m.name)
        end,
      'territory',
        case
          when t.slug is null then null
          else jsonb_build_object('slug', t.slug, 'name', t.name)
        end,
      'timeZone', coalesce(t.timezone, 'Europe/Paris'),
      'timeline', coalesce(tl.entries, '[]'::jsonb),
      'updatedAt', e.updated_at
    )
  into v_public_id, v_data_at, v_payload
  from fire.events e
  left join geo.municipalities m on m.insee_code = e.nearest_municipality_code
  left join app.territories t on t.id = e.territory_id
  left join app.official_messages om on om.id = e.official_status_source_id
  left join lateral (
    select
      array_agg(distinct d.sensor order by d.sensor) as sensors,
      array_agg(distinct d.satellite order by d.satellite) as satellites
    from fire.event_detections ed
    join fire.detections d
      on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
    where ed.event_id = e.id and d.is_public
  ) members on true
  left join lateral (
    select jsonb_agg(
      jsonb_build_object(
        'id', te.id,
        'entryType', te.entry_type,
        'provenance', te.provenance,
        'occurredAt', te.occurred_at,
        'recordedAt', te.recorded_at,
        'title', te.title,
        'summary', te.summary,
        'source',
          case
            when som.id is null then null
            else jsonb_build_object('organisation', som.organisation, 'url', som.source_url)
          end
      )
      order by te.occurred_at desc, te.recorded_at desc
    ) as entries
    from fire.event_timeline_entries te
    left join app.official_messages som on som.id = te.source_id
    where te.event_id = e.id and te.visibility = 'public'
  ) tl on true
  where e.id = target_event_id
    and e.freshness_status <> 'hidden';

  if v_payload is null then
    -- Événement inexistant ou masqué. On ne touche pas au snapshot existant :
    -- le masquage se traite en retirant l'événement de la surface publique,
    -- pas en corrompant son dernier état connu.
    return null;
  end if;

  insert into fire.event_snapshots (event_id, public_id, generated_at, data_at, payload)
  values (target_event_id, v_public_id, v_generated_at, v_data_at, v_payload)
  on conflict (event_id) do update set
    public_id = excluded.public_id,
    generated_at = excluded.generated_at,
    data_at = excluded.data_at,
    payload = excluded.payload;

  update fire.events
  set last_public_snapshot_at = v_generated_at
  where id = target_event_id;

  return v_generated_at;
end;
$$;

comment on function fire.refresh_event_snapshot(uuid) is
  'Reconstruit le snapshot d''un événement, slug éditorial compris. Publication atomique ; en cas d''échec, le snapshot précédent survit intact.';
