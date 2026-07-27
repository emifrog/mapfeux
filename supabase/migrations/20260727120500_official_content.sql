-- =============================================================================
-- 20260727120500 — Liens et messages officiels
--
-- Cahier §5.12, §13.19, §13.20 et §20.4.
--
-- Un message officiel reste attribué à son organisme d'origine. L'interface ne
-- doit jamais permettre de faire passer une note de l'équipe pour une
-- publication d'autorité : c'est l'objet de `organisation` et `source_url`,
-- tous deux obligatoires.
-- =============================================================================

create table app.official_links (
  id uuid primary key default gen_random_uuid(),
  territory_id uuid not null references app.territories (id) on delete cascade,
  category text not null,
  title text not null,
  url text not null,
  organisation text not null,
  display_order integer not null default 0,
  is_active boolean not null default true,
  last_checked_at timestamptz,
  last_http_status integer,
  internal_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint official_links_url_scheme check (url ~* '^https://'),
  constraint official_links_category check (
    category in ('prefecture', 'sdis', 'massif_access', 'vigilance', 'air_quality', 'other')
  )
);

comment on table app.official_links is
  'Liens officiels par territoire, administrables sans déploiement. FR-101.';
comment on column app.official_links.last_http_status is
  'Résultat de la vérification automatique quotidienne. FR-102.';

create index official_links_territory_idx
  on app.official_links (territory_id, display_order)
  where is_active;

create trigger official_links_set_updated_at
  before update on app.official_links
  for each row execute function app.set_updated_at();

alter table app.official_links enable row level security;

-- =============================================================================
-- Messages officiels et bannières
-- =============================================================================

create table app.official_messages (
  id uuid primary key default gen_random_uuid(),
  territory_id uuid references app.territories (id) on delete cascade,
  -- Renseigné lorsque le message concerne un événement précis. Contrainte de
  -- clé étrangère ajoutée avec la table fire.events.
  event_id uuid,
  organisation text not null,
  title text not null,
  body text not null,
  source_url text not null,
  level text not null default 'info',
  -- Heure de publication par l'autorité, distincte de l'heure de saisie.
  published_at timestamptz not null,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_published boolean not null default false,
  created_by uuid not null references admin.profiles (user_id),
  validated_by uuid references admin.profiles (user_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint official_messages_level check (level in ('info', 'important', 'critical')),
  constraint official_messages_source_scheme check (source_url ~* '^https://'),
  constraint official_messages_validity check (valid_to is null or valid_to > valid_from),
  -- Un message publié doit avoir été validé par un second regard. §20.4
  constraint official_messages_published_requires_validation
    check (not is_published or validated_by is not null),
  constraint official_messages_scope check (territory_id is not null or event_id is not null)
);

comment on table app.official_messages is
  'Publications attribuées à une autorité. Provenance official_information (§20.4).';
comment on column app.official_messages.published_at is
  'Date de publication par l''organisme. Sert de référence à official_status_at.';

create index official_messages_active_idx
  on app.official_messages (territory_id, valid_from desc)
  where is_published;

create index official_messages_event_idx
  on app.official_messages (event_id)
  where event_id is not null;

create trigger official_messages_set_updated_at
  before update on app.official_messages
  for each row execute function app.set_updated_at();

alter table app.official_messages enable row level security;
