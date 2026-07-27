-- =============================================================================
-- 20260727120700 — Événements, chronologie et historique
--
-- Cahier §13.6 à §13.10, §5.5, §5.7 et §17.5.
--
-- Les contraintes de cette migration sont la traduction en base des règles
-- appliquées côté applicatif par packages/domain/src/status-transitions.ts.
-- Les deux doivent évoluer ensemble : la base est le dernier rempart, y compris
-- contre un worker mal configuré disposant de `service_role`.
-- =============================================================================

-- Identifiant public opaque, non séquentiel. FR-041.
-- Alphabet Crockford base32 : ni I, ni L, ni O, ni U, afin d'éviter les
-- confusions à la lecture et à la dictée téléphonique.
create or replace function fire.generate_public_id(prefix text default 'MPF')
returns text
language plpgsql
volatile
as $$
declare
  alphabet constant text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  raw bytea := decode(replace(gen_random_uuid()::text, '-', ''), 'hex');
  result text := '';
  i integer;
begin
  for i in 0..7 loop
    result := result || substr(alphabet, (get_byte(raw, i) % 32) + 1, 1);
  end loop;

  return prefix || '-' || result;
end;
$$;

comment on function fire.generate_public_id is
  'Identifiant public partageable. Le préfixe reste configurable tant que la marque n''est pas arrêtée (§15.3).';

-- =============================================================================
-- Événements
-- =============================================================================

create table fire.events (
  id uuid primary key default gen_random_uuid(),
  public_id text not null unique default fire.generate_public_id(),

  -- Dimension 1 : fraîcheur technique, écrite par les traitements automatiques.
  freshness_status fire.freshness_status not null default 'new',

  -- Dimension 2 : niveau de vérification de l'existence.
  verification_status fire.verification_status not null default 'satellite_detection',

  -- Dimension 3 : statut opérationnel officiel, toujours nullable.
  official_control_status fire.official_control_status,
  official_status_source_id uuid references app.official_messages (id) on delete restrict,
  official_status_at timestamptz,
  official_status_set_by uuid references admin.profiles (user_id),

  first_detected_at timestamptz not null,
  last_detected_at timestamptz not null,
  representative_point extensions.geometry(Point, 4326) not null,
  extent extensions.geometry(MultiPolygon, 4326),
  detection_count integer not null default 0,
  sensor_count integer not null default 0,
  confidence_level app.confidence_level not null default 'low',
  confidence_score numeric(4, 3) not null default 0,
  frp_max_mw numeric(10, 3),
  frp_median_mw numeric(10, 3),
  frp_min_mw numeric(10, 3),
  nearest_municipality_code text references geo.municipalities (insee_code),
  territory_id uuid references app.territories (id),
  algorithm_version text not null,
  -- Corrections administratives, conservées à part de l'état calculé. §17.7
  manual_state jsonb not null default '{}'::jsonb,
  hidden_reason text,
  last_public_snapshot_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint events_detection_window check (last_detected_at >= first_detected_at),
  constraint events_counts_non_negative
    check (detection_count >= 0 and sensor_count >= 0),
  constraint events_confidence_range check (confidence_score between 0 and 1),
  constraint events_hidden_requires_reason
    check (freshness_status <> 'hidden' or hidden_reason is not null),

  -- §13.6 : une confirmation officielle exige une source attribuée et datée.
  constraint events_confirmation_requires_attribution check (
    verification_status <> 'officially_confirmed'
    or (official_status_source_id is not null and official_status_at is not null)
  ),

  -- §13.6 : un statut opérationnel exige la même attribution.
  constraint events_official_status_requires_attribution check (
    official_control_status is null
    or (official_status_source_id is not null and official_status_at is not null)
  ),

  -- Renforcement assumé du cahier : un statut opérationnel officiel n'a de sens
  -- que sur un événement dont l'existence est elle-même officiellement
  -- confirmée. Publier « feu éteint » sur un simple regroupement algorithmique
  -- serait une affirmation non sourcée. Voir ADR-011.
  constraint events_official_status_requires_confirmation check (
    official_control_status is null
    or verification_status = 'officially_confirmed'
  )
);

comment on table fire.events is
  'Regroupement algorithmique de détections. Un événement n''est jamais un incendie confirmé par construction (§2.4).';
comment on column fire.events.freshness_status is
  'Fraîcheur technique uniquement. Ne conclut pas sur l''extinction du phénomène.';
comment on column fire.events.official_control_status is
  'Statut opérationnel publié par une autorité. Aucun job ne peut l''écrire (FR-047).';

create index events_last_detected_idx on fire.events (last_detected_at desc);
create index events_point_gix on fire.events using gist (representative_point);
create index events_extent_gix on fire.events using gist (extent);
create index events_territory_idx on fire.events (territory_id, last_detected_at desc);
create index events_public_idx
  on fire.events (last_detected_at desc)
  where freshness_status in ('new', 'recent', 'not_recent');

create trigger events_set_updated_at
  before update on fire.events
  for each row execute function app.set_updated_at();

alter table fire.events enable row level security;

-- Clé étrangère différée jusqu'ici pour éviter une dépendance circulaire entre
-- les messages officiels et les événements.
alter table app.official_messages
  add constraint official_messages_event_fk
  foreign key (event_id) references fire.events (id) on delete cascade;

-- =============================================================================
-- Rattachement des détections
-- =============================================================================

create table fire.event_detections (
  event_id uuid not null references fire.events (id) on delete cascade,
  detection_id uuid not null,
  -- Reprise de la clé de partitionnement, imposée par la clé primaire composite
  -- de fire.detections.
  detection_acquired_at timestamptz not null,
  attached_at timestamptz not null default now(),
  method fire.attachment_method not null,
  score numeric(4, 3),
  algorithm_version text not null,

  primary key (event_id, detection_id, detection_acquired_at),
  constraint event_detections_detection_fk
    foreign key (detection_id, detection_acquired_at)
    references fire.detections (id, acquired_at) on delete cascade,
  -- Une détection appartient à un seul événement à la fois. §13.7
  constraint event_detections_single_event unique (detection_id, detection_acquired_at),
  constraint event_detections_score_range check (score is null or score between 0 and 1)
);

create index event_detections_event_idx on fire.event_detections (event_id, attached_at desc);

alter table fire.event_detections enable row level security;

-- =============================================================================
-- Historique technique — append only
-- =============================================================================

create table fire.event_history (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references fire.events (id) on delete cascade,
  version_no integer not null,
  recorded_at timestamptz not null default now(),
  -- Heure de survenue réelle, distincte de l'heure d'enregistrement. FR-055
  effective_at timestamptz not null,
  change_type text not null,
  provenance app.provenance not null,
  actor_type audit.actor_type not null,
  actor_id uuid,
  source_id uuid,
  algorithm_version text,
  before_state jsonb,
  after_state jsonb not null,
  reason text,
  is_publicly_replayable boolean not null default false,

  constraint event_history_version_unique unique (event_id, version_no)
);

comment on table fire.event_history is
  'Journal append-only permettant de reconstruire l''état logique d''un événement (§13.8).';

create index event_history_event_idx on fire.event_history (event_id, version_no desc);
create index event_history_effective_idx on fire.event_history (effective_at desc);

create trigger event_history_no_update
  before update on fire.event_history
  for each row execute function audit.reject_mutation();

alter table fire.event_history enable row level security;

-- =============================================================================
-- Chronologie narrative
-- =============================================================================

create table fire.event_timeline_entries (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references fire.events (id) on delete cascade,
  entry_type fire.timeline_entry_type not null,
  provenance app.provenance not null,
  occurred_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  title text not null,
  summary text,
  source_id uuid references app.official_messages (id) on delete set null,
  related_entity_type text,
  related_entity_id uuid,
  visibility fire.timeline_visibility not null default 'public',
  -- Idempotence de la génération automatique. FR-058
  deduplication_key text unique,
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references admin.profiles (user_id),

  -- Une information officielle publiée doit être attribuée à sa source. §20.4
  constraint timeline_official_requires_source check (
    provenance <> 'official_information'
    or visibility <> 'public'
    or source_id is not null
  )
);

comment on table fire.event_timeline_entries is
  'Chronologie publique et interne. Les retraits sont logiques : visibility = suppressed (§5.7).';

-- Tri par heure de survenue, indépendamment de l'heure d'import. FR-055
create index timeline_public_idx
  on fire.event_timeline_entries (event_id, occurred_at desc)
  where visibility = 'public';

create index timeline_event_idx on fire.event_timeline_entries (event_id, occurred_at desc);

alter table fire.event_timeline_entries enable row level security;

-- =============================================================================
-- Alias : fusions, séparations et renommages
-- =============================================================================

create table fire.event_aliases (
  public_id text primary key,
  canonical_event_id uuid not null references fire.events (id) on delete cascade,
  reason text not null,
  created_at timestamptz not null default now(),
  created_by uuid references admin.profiles (user_id)
);

comment on table fire.event_aliases is
  'Redirection permanente d''un identifiant fusionné vers l''événement canonique (§13.10).';

create index event_aliases_canonical_idx on fire.event_aliases (canonical_event_id);

alter table fire.event_aliases enable row level security;
