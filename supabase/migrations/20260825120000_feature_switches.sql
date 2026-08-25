-- =============================================================================
-- 20260825120000 — Interrupteurs de fonctions (jalon J8, FR-106 et FR-155)
--
-- Le §18.5 exige que le panache puisse s'éteindre « en une action, sans
-- déploiement », globalement ou par territoire. L'interrupteur vit en base :
-- c'est le seul endroit que le calcul, l'affichage et l'administration lisent
-- tous trois, et une écriture y est immédiate par construction.
--
-- Le registre est générique — `feature` en clé — parce que le panache n'est
-- que le premier : le mode dégradé de J5 (FR-115) et les couches de J9
-- réclameront les mêmes leviers. La sémantique est celle d'un frein :
-- **l'absence de ligne vaut actif**, une ligne `is_enabled = false` coupe.
-- Une ligne sans territoire coupe partout ; une ligne avec territoire ne
-- coupe que lui.
--
-- Toute bascule porte un motif (doctrine du §15.5) et passe par le journal
-- d'audit — c'est le geste d'exploitation (`scripts/toggle-feature.py`) qui
-- l'écrit, la table ne garde que l'état courant.
--
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

create table if not exists app.feature_switches (
  id uuid primary key default gen_random_uuid(),

  feature text not null,
  -- Nul = portée globale. La commune n'est pas une portée : FR-155 parle de
  -- territoires, et c'est à cette maille que l'exploitation raisonne.
  territory_id uuid references app.territories (id) on delete cascade,

  is_enabled boolean not null,
  reason text not null check (length(btrim(reason)) > 0),
  updated_by text not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table app.feature_switches is
  'Interrupteurs de fonctions (FR-106, FR-155). L''absence de ligne vaut actif ; l''état courant seulement, l''historique est au journal d''audit.';

-- Une seule ligne par portée : l'unicité d'un couple à colonne nullable se
-- pose en deux index partiels, pas en contrainte.
create unique index if not exists feature_switches_global_key
  on app.feature_switches (feature)
  where territory_id is null;

create unique index if not exists feature_switches_territory_key
  on app.feature_switches (feature, territory_id)
  where territory_id is not null;

drop trigger if exists feature_switches_set_updated_at on app.feature_switches;
create trigger feature_switches_set_updated_at
  before update on app.feature_switches
  for each row execute function app.set_updated_at();

alter table app.feature_switches enable row level security;

-- La question que tout le monde pose, répondue à un seul endroit : le calcul
-- aujourd'hui, l'affichage et l'API demain. Un interrupteur global coupé
-- l'emporte sur tout ; un interrupteur de territoire ne coupe que les appels
-- qui le nomment.
create or replace function app.is_feature_enabled(feature_key text, territory uuid default null)
returns boolean
language sql
stable
as $$
  select not exists (
    select 1
    from app.feature_switches s
    where s.feature = feature_key
      and not s.is_enabled
      and (s.territory_id is null or s.territory_id = territory)
  );
$$;

comment on function app.is_feature_enabled(text, uuid) is
  'Vrai si rien ne coupe la fonction pour cette portée (FR-106, FR-155). Source unique : calcul, affichage et API doivent tous passer par ici.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    -- Le calcul automatisé lira l'interrupteur ; il ne le bascule jamais —
    -- couper est un geste humain, avec motif.
    grant select on app.feature_switches to mapfeux_ingest;
    grant execute on function app.is_feature_enabled(text, uuid) to mapfeux_ingest;
  end if;
end
$$;
