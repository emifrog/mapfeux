-- =============================================================================
-- 20260727120400 — Registre des sources et journal des imports
--
-- Cahier §9.7, §13.3, §13.4 et §16.1.
--
-- Chaque pipeline ouvre un `import_run` avant tout téléchargement et le clôt
-- même en échec : la page /statut se lit intégralement dans cette table.
-- =============================================================================

create table ingest.data_sources (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  name text not null,
  provider text not null,
  expected_interval interval not null,
  stale_after interval not null,
  status ingest.source_status not null default 'active',
  documentation_url text,
  license_name text,
  attribution text not null,
  contact text,
  retention_policy text,
  last_contract_check_on date,
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint data_sources_key_format check (key ~ '^[a-z][a-z0-9_]*$'),
  constraint data_sources_stale_after_gt_interval check (stale_after >= expected_interval)
);

comment on table ingest.data_sources is
  'Registre des fournisseurs : licence, attribution et seuils de retard. Cahier §9.7.';
comment on column ingest.data_sources.settings is
  'Configuration NON secrète. Les clés API vivent dans l''environnement du worker (§14.3).';

create trigger data_sources_set_updated_at
  before update on ingest.data_sources
  for each row execute function app.set_updated_at();

alter table ingest.data_sources enable row level security;

-- =============================================================================
-- Exécutions d'import
-- =============================================================================

create table ingest.import_runs (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references ingest.data_sources (id) on delete restrict,
  job_name text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status ingest.run_status not null default 'running',
  -- Date des données elles-mêmes, distincte de l'heure d'import. FR-005
  source_data_at timestamptz,
  records_read integer not null default 0,
  records_inserted integer not null default 0,
  records_updated integer not null default 0,
  records_rejected integer not null default 0,
  artifact_path text,
  checksum text,
  error_code text,
  -- Résumé interne : jamais exposé au public tel quel. FR-112
  error_summary text,
  metrics jsonb not null default '{}'::jsonb,

  constraint import_runs_finished_after_started
    check (finished_at is null or finished_at >= started_at),
  constraint import_runs_terminal_has_finished_at
    check (status = 'running' or finished_at is not null),
  constraint import_runs_failure_has_code
    check (status <> 'failed' or error_code is not null),
  constraint import_runs_counts_non_negative
    check (
      records_read >= 0
      and records_inserted >= 0
      and records_updated >= 0
      and records_rejected >= 0
    )
);

comment on table ingest.import_runs is
  'Journal des imports, base de la page /statut et des incidents. Cahier §13.4.';

create index import_runs_source_started_idx
  on ingest.import_runs (source_id, started_at desc);

create index import_runs_status_idx
  on ingest.import_runs (status, started_at desc)
  where status in ('running', 'failed', 'partial');

-- Un seul import en cours par source et par tâche : garde-fou complémentaire du
-- verrou distribué côté worker. §16.1
create unique index import_runs_single_running
  on ingest.import_runs (source_id, job_name)
  where status = 'running';

alter table ingest.import_runs enable row level security;

-- =============================================================================
-- Incidents
-- =============================================================================

create table ingest.incidents (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references ingest.data_sources (id) on delete restrict,
  opened_at timestamptz not null default now(),
  acknowledged_at timestamptz,
  resolved_at timestamptz,
  acknowledged_by uuid references admin.profiles (user_id),
  failure_count integer not null default 1,
  error_code text,
  -- Message compréhensible destiné à la page publique /statut. FR-112
  public_message text not null,
  internal_notes text,

  constraint incidents_resolution_order
    check (resolved_at is null or resolved_at >= opened_at)
);

comment on table ingest.incidents is
  'Incident ouvert automatiquement après plusieurs échecs consécutifs. FR-113.';

create index incidents_open_idx
  on ingest.incidents (source_id, opened_at desc)
  where resolved_at is null;

alter table ingest.incidents enable row level security;
