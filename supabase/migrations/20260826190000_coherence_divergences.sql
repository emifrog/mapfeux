-- =============================================================================
-- 20260826190000 — Alerte de cohérence observation / statut officiel (J4)
--
-- Cahier v2.1 §17.4, §17.5, FR-145. Une détection postérieure à un statut
-- officiel ne le modifie jamais en silence : elle génère une **alerte de
-- cohérence pour revue** — une entrée du journal d'audit — et la fiche
-- affiche la divergence sans écraser l'une des deux informations.
--
-- Seul « éteint » diverge d'une observation postérieure : « circonscrit »
-- et « maîtrisé » annoncent par définition une activité qui continue sous
-- contrôle — signaler une divergence sur ces statuts apprendrait à ignorer
-- l'alerte, la leçon de la vigilance. Le même choix vit côté web dans
-- `packages/domain/src/coherence.ts` : deux chemins, une définition.
--
-- Le rôle d'ingestion n'a **aucun accès au journal d'audit**, et c'est
-- voulu (migration du rôle, doctrine en tête de fichier) : la fonction est
-- `security definer` — le rôle reçoit la capacité étroite de signaler une
-- divergence au format fixé, jamais le journal. La déduplication vit dans
-- la fonction : une divergence est signalée **une fois par statut** — de
-- nouvelles observations n'empilent pas d'alertes, un nouveau statut
-- ré-ouvre la vigilance.
--
-- Idempotente ; signature qualifiée.
-- =============================================================================

create or replace function fire.flag_official_status_divergences()
returns table (
  public_id text,
  official_status_at timestamptz,
  last_detected_at timestamptz
)
language sql
volatile
security definer
set search_path = fire, audit, pg_temp
as $$
  with divergent as (
    select
      e.public_id,
      e.official_control_status,
      e.official_status_at,
      e.last_detected_at,
      e.detection_count
    from fire.events e
    where e.official_control_status = 'extinguished'
      and e.official_status_at is not null
      and e.last_detected_at > e.official_status_at
      and not exists (
        select 1
        from audit.entries a
        where a.resource_type = 'fire.events'
          and a.resource_id = e.public_id
          and a.action = 'coherence_observation_apres_statut_officiel'
          and (a.after_state->>'official_status_at')::timestamptz = e.official_status_at
      )
  ),
  flagged as (
    insert into audit.entries
      (actor_type, actor_label, action, resource_type, resource_id, after_state)
    select
      'system',
      'geo-worker',
      'coherence_observation_apres_statut_officiel',
      'fire.events',
      d.public_id,
      jsonb_build_object(
        'official_control_status', d.official_control_status,
        'official_status_at', d.official_status_at,
        'last_detected_at', d.last_detected_at,
        'detection_count', d.detection_count
      )
    from divergent d
    returning
      resource_id,
      (after_state->>'official_status_at')::timestamptz,
      (after_state->>'last_detected_at')::timestamptz
  )
  select * from flagged;
$$;

comment on function fire.flag_official_status_divergences() is
  'Alerte de cohérence §17.4 : journalise une fois par statut les événements « éteints » observés après leur statut. Le rôle d''ingestion appelle, jamais n''écrit le journal.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mapfeux_ingest') then
    grant execute on function fire.flag_official_status_divergences() to mapfeux_ingest;
  end if;
end
$$;
