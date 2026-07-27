-- =============================================================================
-- 20260727120200 — Profils administrateurs et journal d'audit
--
-- Cahier §13.21, §13.22, §14.1 et §14.4.
--
-- Le rôle applicatif est porté par cette table, pas par les métadonnées du JWT
-- côté client : un jeton ne doit jamais pouvoir s'auto-attribuer un rôle.
-- =============================================================================

create table admin.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  role admin.role not null default 'viewer_admin',
  status admin.profile_status not null default 'invited',
  display_name text not null,
  -- Territoires autorisés. NULL = portée nationale (cahier §14.2).
  allowed_territory_ids uuid[],
  mfa_required boolean not null default false,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table admin.profiles is
  'Habilitations administrateur. Seule source de vérité des rôles (cahier §14.2).';

create index profiles_role_idx on admin.profiles (role) where status = 'active';

create trigger profiles_set_updated_at
  before update on admin.profiles
  for each row execute function app.set_updated_at();

-- MFA obligatoire pour les super administrateurs. §14.4
alter table admin.profiles
  add constraint profiles_super_admin_requires_mfa
  check (role <> 'super_admin' or mfa_required);

alter table admin.profiles enable row level security;
alter table admin.profiles force row level security;

-- Un administrateur peut lire son propre profil, jamais celui des autres.
create policy profiles_self_select on admin.profiles
  for select to authenticated
  using (user_id = (select auth.uid()));

-- =============================================================================
-- Fonctions d'habilitation
-- =============================================================================

-- Nommée `effective_role` et non `current_role` : CURRENT_ROLE est un mot-clé
-- réservé SQL, inutilisable comme nom de fonction même qualifié par son schéma.
create or replace function admin.effective_role()
returns admin.role
language sql
stable
security definer
set search_path = admin, pg_temp
as $$
  select p.role
  from admin.profiles p
  where p.user_id = auth.uid()
    and p.status = 'active';
$$;

comment on function admin.effective_role is
  'Rôle effectif de l''appelant, ou NULL s''il n''est pas administrateur actif.';

create or replace function admin.has_role(required variadic admin.role[])
returns boolean
language sql
stable
security definer
set search_path = admin, pg_temp
as $$
  select coalesce(admin.effective_role() = any(required), false);
$$;

-- =============================================================================
-- Journal d'audit — append only
-- =============================================================================

create table audit.entries (
  id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  actor_type audit.actor_type not null,
  actor_id uuid,
  actor_label text,
  action text not null,
  resource_type text not null,
  resource_id text,
  before_state jsonb,
  after_state jsonb,
  reason text,
  -- Adresse IP hachée si la conservation est justifiée. Jamais en clair. §13.22
  ip_hash text,
  user_agent_summary text
);

comment on table audit.entries is
  'Journal immuable des actions sensibles. Aucune mise à jour ni suppression.';

create index audit_entries_occurred_at_idx on audit.entries (occurred_at desc);
create index audit_entries_resource_idx on audit.entries (resource_type, resource_id);
create index audit_entries_actor_idx on audit.entries (actor_id, occurred_at desc);

-- Une action humaine sur une ressource exige un motif enregistré. §15.5
alter table audit.entries
  add constraint audit_entries_admin_requires_reason
  check (actor_type <> 'admin' or (reason is not null and length(btrim(reason)) > 0));

alter table audit.entries enable row level security;
alter table audit.entries force row level security;

-- Immuabilité vérifiée en base : `service_role` lui-même ne peut pas réécrire
-- l'historique. La rétention se fait par partition ou archivage, pas par UPDATE.
create or replace function audit.reject_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Le journal d''audit est append-only (cahier §13.22).'
    using errcode = 'restrict_violation';
end;
$$;

create trigger audit_entries_no_update
  before update on audit.entries
  for each row execute function audit.reject_mutation();

create trigger audit_entries_no_delete
  before delete on audit.entries
  for each row execute function audit.reject_mutation();
