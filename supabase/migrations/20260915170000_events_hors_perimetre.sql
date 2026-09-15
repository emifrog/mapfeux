-- =============================================================================
-- 20260915170000 — Un événement hors du périmètre n'est pas publié
--
-- Cahier v2.1 §2.4, FR-001 (« France métropolitaine et Corse »), §17.7.
-- ADR-027.
--
-- Trouvé le 15 septembre 2026 : la zone d'import FIRMS est un rectangle qui
-- déborde des frontières, et chaque événement reçoit la commune française la
-- plus proche, quelle que soit la distance. Sur sept jours, 716 événements
-- publiés, 322 en France ; « près de Condé-sur-l'Escaut » désignait un site
-- industriel belge à quatre-vingts kilomètres. Le périmètre du service était
-- écrit partout et appliqué nulle part.
--
-- ## Ce qui est décidé (ADR-027)
--
-- Les détections hors périmètre restent **importées** — la donnée brute est
-- archivée de toute façon (§16.1), et rien n'est détruit — mais l'événement
-- qu'elles forment n'est **jamais publié**. Le mécanisme est celui qui existe
-- déjà pour le retrait éditorial : `freshness_status = 'hidden'`, que toutes
-- les fonctions publiques honorent (§17.7), avec un motif qui dit pourquoi.
-- Une seule règle, un seul endroit, aucune fonction publique à réécrire.
--
-- ## Ce qui fait « dans le périmètre »
--
-- La règle des agrégats (47ᵉ migration) : dans le polygone d'un département,
-- ou à moins de 0,05 degré de l'un d'eux — le littoral. `fire.events` porte
-- le verdict en colonne (`in_territory`), posé par un déclencheur à chaque
-- insertion et à chaque déplacement du point représentatif, pour que
-- l'admin et les mesures puissent le lire sans le recalculer.
--
-- Le déclencheur force `hidden` tant que l'événement est hors périmètre, quel
-- que soit le chemin — regroupement, cycle de vie, retouche manuelle — et
-- rend la main au cycle de vie si le point revient dans le périmètre (le
-- motif est reconnu, jamais deviné). Le regroupement **continue d'alimenter**
-- un événement masqué (`clustering.py` n'écarte que `archived`) : un site
-- étranger reste un seul événement masqué au lieu d'en engendrer un par
-- passe, et c'est ce rattachement qui peut ramener son point dans le
-- périmètre. (Commentaire corrigé le soir du 15 septembre 2026 : la version
-- initiale disait l'inverse ; le SQL de cette migration n'a pas changé.)
--
-- Idempotente : `add column if not exists`, `create or replace`, déclencheur
-- reposé après suppression, rattrapage borné aux lignes à changer.
-- =============================================================================

alter table fire.events
  add column if not exists in_territory boolean not null default true;

comment on column fire.events.in_territory is
  'Le point représentatif est en France métropolitaine ou en Corse — dans un '
  'département, ou à moins de 0,05° de l''un d''eux. Posé par déclencheur. Faux : '
  'l''événement est masqué (`hidden`, motif « hors périmètre »). ADR-027.';

create index if not exists events_outside_territory_idx
  on fire.events (in_territory)
  where not in_territory;

-- Même règle que les agrégats départementaux (47ᵉ migration).
create or replace function fire.point_in_territory(point extensions.geometry)
returns boolean
language sql
stable
set search_path = app, extensions, pg_temp
as $$
  select exists (
    select 1
    from app.territories t
    where t.type = 'department'
      and t.geometry is not null
      and extensions.st_dwithin(t.geometry, point, 0.05)
  );
$$;

comment on function fire.point_in_territory(extensions.geometry) is
  'Le point est dans un département, ou à moins de 0,05° de l''un d''eux — le '
  'littoral. La règle du périmètre du service, en un seul endroit. ADR-027.';

create or replace function fire.enforce_territory()
returns trigger
language plpgsql
set search_path = fire, extensions, pg_temp
as $$
declare
  perimeter_reason constant text := 'hors périmètre : France métropolitaine et Corse';
begin
  new.in_territory := fire.point_in_territory(new.representative_point);

  if not new.in_territory then
    -- Hors périmètre : masqué, avec le motif — quel que soit le chemin qui
    -- écrit. Un motif éditorial déjà posé est conservé : il dit plus.
    new.freshness_status := 'hidden';
    new.hidden_reason := coalesce(new.hidden_reason, perimeter_reason);
  elsif tg_op = 'UPDATE'
    and old.freshness_status = 'hidden'
    and new.freshness_status = 'hidden'
    and new.hidden_reason = perimeter_reason then
    -- Revenu dans le périmètre, et masqué pour cette seule raison : la main
    -- revient au cycle de vie, qui requalifiera à sa prochaine passe.
    new.freshness_status := 'new';
    new.hidden_reason := null;
  end if;

  return new;
end;
$$;

comment on function fire.enforce_territory() is
  'Pose `in_territory` et masque tout événement hors périmètre, à chaque '
  'écriture. ADR-027.';

drop trigger if exists events_enforce_territory on fire.events;
create trigger events_enforce_territory
  before insert or update on fire.events
  for each row
  execute function fire.enforce_territory();

-- Rattrapage, borné aux lignes qui changent : rejouable sans effet.
update fire.events e
set in_territory = fire.point_in_territory(e.representative_point)
where e.in_territory <> fire.point_in_territory(e.representative_point)
   or (not fire.point_in_territory(e.representative_point) and e.freshness_status <> 'hidden');

-- Pour la fiche : dire pourquoi un identifiant partagé ne mène à rien,
-- plutôt qu'un 404 muet. Ne révèle que le fait d'être hors périmètre.
create or replace function api.event_outside_territory(event_public_id text)
returns boolean
language sql
stable
security definer
set search_path = fire, pg_temp
as $$
  select exists (
    select 1
    from fire.events e
    where e.public_id = event_public_id
      and not e.in_territory
  );
$$;

comment on function api.event_outside_territory(text) is
  'Vrai si l''identifiant désigne un événement hors du périmètre du service — '
  'importé, jamais publié. Pour que la fiche le dise. ADR-027.';

grant execute on function api.event_outside_territory(text) to anon, authenticated;

notify pgrst, 'reload schema';
