-- =============================================================================
-- 20260828100000 — Niveaux d'accès aux massifs forestiers (J4)
--
-- Cahier v2.1 §9.2 et §20.4, FR-140/FR-142 ; ADR-026.
--
-- Les préfectures méditerranéennes publient chaque jour, sur le site
-- interservices risque-prevention-incendie.fr, le niveau d'accès de chaque
-- massif (0 à 5, du vert au rouge exceptionnel) — la carte quotidienne que
-- les arrêtés d'accès aux massifs rendent opposable. La capture range un
-- niveau **par massif et par jour**, avec le libellé officiel du site
-- (« Accès interdit, travaux interdits »… — chaque département a son
-- vocabulaire, republié verbatim, jamais réécrit).
--
-- Une révision intra-journalière (ré-émission exceptionnelle) remplace le
-- niveau du jour : la valeur courante est la vérité opposable, et chaque
-- passe archive le JSON brut — l'historique des révisions vit dans `raw`
-- et au journal des imports, pas dans cette table.
--
-- Idempotente ; signatures qualifiées.
-- =============================================================================

create table if not exists app.massif_access_levels (
  id uuid primary key default gen_random_uuid(),

  department_code text not null,
  massif_id text not null,
  massif_name text not null,
  valid_on date not null,

  level smallint not null,
  procedure_flag smallint,
  -- Le libellé du site officiel pour ce niveau, au moment de la capture :
  -- c'est lui qui s'affiche, jamais une reformulation de MapFeux.
  level_label text,
  source_url text not null,

  first_captured_at timestamptz not null default now(),
  last_captured_at timestamptz not null default now(),
  import_run_id uuid references ingest.import_runs (id) on delete set null,

  constraint massif_access_levels_unique unique (department_code, massif_id, valid_on),
  constraint massif_access_levels_level_range check (level between 0 and 5),
  constraint massif_access_levels_source_scheme check (source_url ~* '^https://')
);

comment on table app.massif_access_levels is
  'Niveau quotidien d''accès par massif forestier, capté du site interservices des préfectures. ADR-026, FR-140.';
comment on column app.massif_access_levels.level_label is
  'Libellé officiel du niveau, verbatim du site source au moment de la capture.';

create index if not exists massif_access_levels_day_idx
  on app.massif_access_levels (department_code, valid_on desc);

alter table app.massif_access_levels enable row level security;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant select, insert, update on app.massif_access_levels to mapfeux_ingest;
  end if;
end
$$;

-- Les niveaux servables d'un département : aujourd'hui et demain quand la
-- prévision de 18 h est déjà captée. Jamais d'historique ici — un niveau
-- passé n'est plus opposable et l'afficher inviterait à s'y fier.
create or replace function api.department_massif_levels(department text)
returns table (
  massif_name text,
  valid_on date,
  level smallint,
  level_label text,
  source_url text,
  last_captured_at timestamptz
)
language sql
stable
security definer
set search_path = app, pg_temp
as $$
  select m.massif_name, m.valid_on, m.level, m.level_label, m.source_url, m.last_captured_at
  from app.massif_access_levels m
  where m.department_code = department
    and m.valid_on >= current_date
  order by m.valid_on, m.massif_name;
$$;

comment on function api.department_massif_levels(text) is
  'Niveaux d''accès aux massifs d''un département, aujourd''hui et demain. Libellés verbatim du site officiel. ADR-026, FR-140.';

grant execute on function api.department_massif_levels(text) to anon, authenticated;
