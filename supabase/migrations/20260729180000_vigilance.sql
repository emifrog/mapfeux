-- =============================================================================
-- 20260729180000 — Vigilance météorologique Météo-France
--
-- Stratégie §4 : la vigilance fait partie des sources officielles ajoutées au
-- MVP. Le cahier ne la prévoyait que comme un lien (FR-100).
--
-- La vigilance n'est pas un « message officiel » au sens de
-- `app.official_messages`, et l'y loger serait une erreur de modèle à deux
-- titres. D'abord cette table exige un `created_by` humain et un `validated_by`
-- avant publication, ce qu'une ingestion automatique n'a pas — il faudrait
-- inventer un auteur. Ensuite la vigilance est une donnée **structurée** :
-- département, phénomène, couleur, fenêtre de validité. La réduire à un titre
-- et un corps de texte perdrait précisément ce qui permet de l'afficher.
--
-- ## Provenance
--
-- Le format V6 est décrit par « Descriptif technique des informations Vigilance
-- METROPOLE » de Météo-France. Les correspondances de codes ci-dessous en sont
-- tirées, pas devinées : publier « orange » pour le mauvais phénomène serait la
-- désinformation que le cahier §2.4 interdit.
--
-- Licence Ouverte Etalab v2, attribution « Source : Météo-France ».
-- =============================================================================

create type meteo.vigilance_colour as enum ('vert', 'jaune', 'orange', 'rouge');

comment on type meteo.vigilance_colour is
  'Couleurs de la carte de Vigilance. color_id 1 à 4 du format V6.';

-- Référentiel des phénomènes, figé par le descriptif technique. En table plutôt
-- qu'en enum : un phénomène ajouté par Météo-France doit pouvoir être ingéré
-- sans migration bloquante, quitte à être affiché sans libellé français.
create table meteo.vigilance_phenomena (
  id smallint primary key,
  label text not null,
  -- Un feu se propage avec le vent, s'allume sous l'orage et prospère sur la
  -- sécheresse. Les autres phénomènes sont ingérés et conservés, mais ce
  -- drapeau permet de les distinguer à l'affichage sans les masquer (§17.7).
  relevant_to_fire boolean not null default false
);

insert into meteo.vigilance_phenomena (id, label, relevant_to_fire) values
  (1, 'Vent violent', true),
  (2, 'Pluie-inondation', false),
  (3, 'Orages', true),
  (4, 'Crues', false),
  (5, 'Neige-verglas', false),
  (6, 'Canicule', true),
  (7, 'Grand froid', false),
  (8, 'Avalanches', false),
  (9, 'Vagues-submersion', false);

comment on table meteo.vigilance_phenomena is
  'Phénomènes du format Vigilance V6, d''après le descriptif technique Météo-France.';

-- =============================================================================
-- Bulletins
-- =============================================================================

create table meteo.vigilance_bulletins (
  id uuid primary key default gen_random_uuid(),

  -- « FRA » pour la métropole. Le format prévoit d'autres domaines produits.
  domain_id text not null,
  vigilance_version text not null,
  format_version text not null,

  -- Heure de **diffusion** par Météo-France, distincte de l'heure d'import.
  -- C'est elle qui fait la fraîcheur affichée (§5.13).
  published_at timestamptz not null,
  -- Identifiant de la saisie validée des prévisionnistes, utile au diagnostic.
  snapshot_id text,

  source_url text not null,
  checksum text not null,
  -- Charge utile conservée telle quelle : la chronologie détaillée par plages
  -- de couleur n'est pas dépliée dans `vigilance_levels`, et ce qui n'a pas été
  -- conservé ne peut pas être rejoué (§12.4).
  raw jsonb not null,

  import_run_id uuid references ingest.import_runs (id) on delete set null,
  imported_at timestamptz not null default now(),

  constraint vigilance_bulletins_source_scheme check (source_url ~* '^https://'),
  -- Rejouer un import ne doit pas dupliquer un bulletin déjà connu.
  constraint vigilance_bulletins_unique unique (domain_id, published_at)
);

create index vigilance_bulletins_recent_idx
  on meteo.vigilance_bulletins (published_at desc);

alter table meteo.vigilance_bulletins enable row level security;

-- =============================================================================
-- Niveaux par domaine, échéance et phénomène
-- =============================================================================

create table meteo.vigilance_levels (
  bulletin_id uuid not null
    references meteo.vigilance_bulletins (id) on delete cascade,

  -- « 06 » pour un département, « 0610 » pour son pourtour littoral, « FRA »
  -- pour le national, « ZDF_xxx » pour une zone de défense.
  domain_id text not null,
  -- Extrait du domaine quand il en désigne un. Null pour FRA et les zones de
  -- défense : y forcer une valeur inventerait un rattachement.
  department_code text,
  is_coastal boolean not null default false,

  -- « J » ou « J1 ». Avant six heures locales, le produit ne porte que « J ».
  echeance text not null,
  phenomenon_id smallint not null references meteo.vigilance_phenomena (id),

  -- Couleur **maximale** du phénomène sur l'échéance, soit
  -- `phenomenon_max_color_id`. Lire la chronologie à la place ferait perdre les
  -- crues, dont le descriptif précise que les tableaux de chronologie sont
  -- vides pour J et J1.
  colour meteo.vigilance_colour not null,

  begin_at timestamptz not null,
  end_at timestamptz not null,

  primary key (bulletin_id, domain_id, echeance, phenomenon_id),
  constraint vigilance_levels_echeance check (echeance in ('J', 'J1')),
  constraint vigilance_levels_validity check (end_at > begin_at)
);

create index vigilance_levels_department_idx
  on meteo.vigilance_levels (department_code, echeance)
  where department_code is not null and colour <> 'vert';

comment on column meteo.vigilance_levels.colour is
  'Couleur maximale du phénomène sur l''échéance (phenomenon_max_color_id).';

alter table meteo.vigilance_levels enable row level security;

-- =============================================================================
-- Droits de l'ingestion automatisée
-- =============================================================================

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant usage on schema meteo to mapfeux_ingest;
    grant select on meteo.vigilance_phenomena to mapfeux_ingest;
    grant select, insert on meteo.vigilance_bulletins to mapfeux_ingest;
    grant select, insert on meteo.vigilance_levels to mapfeux_ingest;
  end if;
end
$$;
