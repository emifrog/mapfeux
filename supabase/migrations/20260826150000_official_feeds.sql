-- =============================================================================
-- 20260826150000 — Liste blanche et capture des publications officielles (J4)
--
-- Cahier v2.1 §9.2, §20.4, FR-140 à FR-143 ; ADR-026 (stratégie §8.3,
-- tranchée le 26 août : republication automatique en liste blanche).
--
-- Deux tables, distinctes du modèle éditorial `app.official_messages` — qui
-- garde son auteur et son second valideur — comme la vigilance a les
-- siennes :
--
-- `official_feeds` est la **liste blanche** : une ligne par page ou flux
-- d'autorité capté, administrable sans déploiement. Y entrer est un acte
-- d'administration qui engage (ADR-026).
--
-- `official_feed_items` est la **citation datée** : titre verbatim, lien
-- vers la source, date de publication de l'autorité. Jamais de résumé ni
-- de reformulation. `is_public` permet de masquer une erreur de capture
-- sans la détruire — un geste d'exploitation, pas une validation préalable.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

create table if not exists app.official_feeds (
  id uuid primary key default gen_random_uuid(),

  organisation text not null,
  feed_url text not null,
  -- Sélecteur d'analyseur : la page « Actualités » des sites préfectoraux
  -- nouvelle génération (les flux RSS y ont disparu), d'autres formes
  -- viendront par ajout, jamais par devinette.
  kind text not null default 'actualites_page',
  department_code text,

  is_active boolean not null default true,
  last_polled_at timestamptz,
  last_http_status integer,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint official_feeds_url_unique unique (feed_url),
  -- Une autorité publie sur le domaine de l'État : la liste blanche ne
  -- capte rien d'autre (ADR-026).
  constraint official_feeds_url_scheme check (feed_url ~* '^https://'),
  constraint official_feeds_kind check (kind in ('actualites_page'))
);

comment on table app.official_feeds is
  'Liste blanche des pages et flux d''autorité captés automatiquement. ADR-026, cahier §9.2.';

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'official_feeds_set_updated_at'
      and tgrelid = 'app.official_feeds'::regclass
  ) then
    create trigger official_feeds_set_updated_at
      before update on app.official_feeds
      for each row execute function app.set_updated_at();
  end if;
end
$$;

alter table app.official_feeds enable row level security;

create table if not exists app.official_feed_items (
  id uuid primary key default gen_random_uuid(),
  feed_id uuid not null references app.official_feeds (id) on delete cascade,

  -- Verbatim de l'autorité : le titre tel que publié, l'URL de la
  -- publication, la date annoncée — au jour, c'est ce que la page donne,
  -- aucune heure n'est inventée.
  title text not null,
  url text not null,
  published_on date,

  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  import_run_id uuid references ingest.import_runs (id) on delete set null,

  -- Masquage sans destruction : le retrait d'une erreur de capture est un
  -- geste d'exploitation (ADR-026), jamais une suppression.
  is_public boolean not null default true,

  constraint official_feed_items_unique unique (feed_id, url),
  constraint official_feed_items_url_scheme check (url ~* '^https://')
);

comment on table app.official_feed_items is
  'Publications d''autorité captées : citations datées, jamais réécrites. ADR-026, FR-141/FR-142.';
comment on column app.official_feed_items.published_on is
  'Date annoncée par l''autorité (« Publié le »), au jour — aucune heure n''est inventée.';

create index if not exists official_feed_items_feed_idx
  on app.official_feed_items (feed_id, published_on desc)
  where is_public;

alter table app.official_feed_items enable row level security;

-- Le rôle d'ingestion lit la liste blanche, tient son état de sonde et
-- écrit les captures. Jamais de delete : le masquage passe par is_public.
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant select, update on app.official_feeds to mapfeux_ingest;
    grant select, insert, update on app.official_feed_items to mapfeux_ingest;
  end if;
end
$$;
