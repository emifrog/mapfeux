-- =============================================================================
-- 20260728120000 — Snapshots publics par événement
--
-- Cahier §21.5 et FR-052.
--
-- Un snapshot est une vue figée et cohérente de la fiche, reconstruite après
-- chaque évolution significative de l'événement. Il répond à trois besoins :
--
--   1. **Cohérence.** La fiche vive assemble plusieurs requêtes ; entre deux
--      d'entre elles, un import peut modifier les agrégats. Le snapshot est
--      construit en une transaction, donc jamais à moitié à jour.
--   2. **Dernier état connu.** Si un recalcul échoue ou si une source tombe, le
--      snapshot précédent reste servi, avec sa date de génération et la date de
--      la donnée qu'il porte — jamais présenté comme actuel (§21.5).
--   3. **Coût de lecture.** Une lecture d'une ligne remplace plusieurs jointures
--      au moment précis où le trafic explose.
--
-- Ce qu'un snapshot ne fait PAS : protéger d'une panne de la base, puisqu'il y
-- réside. Cette protection-là est portée par le cache HTTP et la revalidation
-- côté Next.js.
--
-- Un seul snapshot courant par événement. L'historique rejouable est porté par
-- `fire.event_history`, qui est append-only : le snapshot est un cache de
-- rendu, pas une trace d'audit. Confondre les deux ferait grossir sans fin une
-- table dont la seule raison d'être est d'être lue vite.
-- =============================================================================

create table fire.event_snapshots (
  event_id uuid primary key references fire.events (id) on delete cascade,
  public_id text not null,
  -- Heure de construction du snapshot.
  generated_at timestamptz not null default now(),
  -- Heure de la donnée la plus récente qu'il contient. Les deux sont
  -- distinctes et toutes deux affichées : un snapshot fraîchement reconstruit
  -- peut porter une observation vieille de trois jours (§21.5).
  data_at timestamptz not null,
  payload jsonb not null,
  algorithm_version text not null default 'snapshot-v1'
);

comment on table fire.event_snapshots is
  'Vue figée de la fiche événement. Cache de rendu, pas trace d''audit (§21.5).';
comment on column fire.event_snapshots.data_at is
  'Date de la donnée portée, distincte de generated_at. Jamais confondues.';

create index event_snapshots_public_id_idx on fire.event_snapshots (public_id);
create index event_snapshots_generated_at_idx on fire.event_snapshots (generated_at desc);

alter table fire.event_snapshots enable row level security;

-- =============================================================================
-- Construction
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

comment on function fire.refresh_event_snapshot is
  'Reconstruit le snapshot d''un événement. Publication atomique ; en cas d''échec, le snapshot précédent survit intact.';

-- =============================================================================
-- Lecture publique
-- =============================================================================

create or replace function api.fire_event_snapshot(event_public_id text)
returns table (
  generated_at timestamptz,
  data_at timestamptz,
  payload jsonb
)
language sql
stable
security definer
set search_path = fire, pg_temp
as $$
  select s.generated_at, s.data_at, s.payload
  from fire.event_snapshots s
  join fire.events e on e.id = s.event_id
  where s.public_id = event_public_id
    -- Un événement masqué disparaît aussi de ses snapshots.
    and e.freshness_status <> 'hidden';
$$;

comment on function api.fire_event_snapshot is
  'Dernier état publiable d''un événement, avec ses deux horodatages (FR-052).';

grant execute on function api.fire_event_snapshot(text) to anon, authenticated;
