-- =============================================================================
-- 20260826170000 — Rapprochement et surface publique des citations (J4)
--
-- Cahier v2.1 §20.4, FR-104, FR-110/FR-114 par analogie ; ADR-026.
--
-- Le rapprochement d'une citation à un événement est un **appariement de
-- structure**, jamais une lecture : les codes INSEE des communes dont le
-- nom entier figure dans le titre (détection côté worker, frontière de
-- mot, sans accent) rencontrent la commune la plus proche de l'événement,
-- dans une fenêtre temporelle autour de son activité. Le critère
-- d'affichage EST la définition du rapprochement — la fiche ne dira
-- jamais plus que « publication de la préfecture mentionnant la commune ».
--
-- Idempotente ; signatures qualifiées (leçon des 42701/42725).
-- =============================================================================

alter table app.official_feed_items
  add column if not exists municipality_insee_codes text[] not null default '{}';

comment on column app.official_feed_items.municipality_insee_codes is
  'Communes dont le nom entier figure dans le titre — appariement de structure (frontière de mot, sans accent), jamais une lecture du texte.';

create index if not exists official_feed_items_municipalities_idx
  on app.official_feed_items using gin (municipality_insee_codes)
  where is_public;

-- Les citations d'un département, pour sa page territoire.
create or replace function api.department_official_items(department text)
returns table (
  organisation text,
  title text,
  url text,
  published_on date,
  first_seen_at timestamptz
)
language sql
stable
security definer
set search_path = app, pg_temp
as $$
  select f.organisation, i.title, i.url, i.published_on, i.first_seen_at
  from app.official_feed_items i
  join app.official_feeds f on f.id = i.feed_id
  where f.department_code = department
    and f.is_active
    and i.is_public
  order by i.published_on desc nulls last, i.first_seen_at desc
  limit 20;
$$;

comment on function api.department_official_items(text) is
  'Citations captées d''un département : republication attribuée, jamais réécrite. ADR-026, FR-141/FR-142.';

grant execute on function api.department_official_items(text) to anon, authenticated;

-- Les citations rapprochées d'un événement : commune mentionnée = commune
-- la plus proche, dans une fenêtre de 7 jours avant la première détection
-- à 14 jours après la dernière — les interdictions précèdent, les points
-- de situation suivent.
create or replace function api.fire_event_official_items(event_public_id text)
returns table (
  organisation text,
  title text,
  url text,
  published_on date,
  municipality_name text
)
language sql
stable
security definer
set search_path = app, fire, geo, pg_temp
as $$
  select f.organisation, i.title, i.url, i.published_on, m.name
  from fire.events e
  join geo.municipalities m on m.insee_code = e.nearest_municipality_code
  join app.official_feed_items i on i.municipality_insee_codes @> array[m.insee_code]
  join app.official_feeds f on f.id = i.feed_id
  where e.public_id = event_public_id
    and e.freshness_status <> 'hidden'
    and f.is_active
    and i.is_public
    and i.published_on is not null
    and i.published_on
      between ((e.first_detected_at at time zone 'utc')::date - 7)
          and ((e.last_detected_at at time zone 'utc')::date + 14)
  order by i.published_on desc;
$$;

comment on function api.fire_event_official_items(text) is
  'Citations préfectorales mentionnant la commune de l''événement, dans la fenêtre de son activité. Appariement de structure, ADR-026.';

grant execute on function api.fire_event_official_items(text) to anon, authenticated;
