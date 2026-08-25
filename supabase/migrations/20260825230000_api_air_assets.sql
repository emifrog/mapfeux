-- =============================================================================
-- 20260825230000 — Surface publique des rasters de qualité de l'air (J9)
--
-- Cahier v2.1 §19.2 et FR-121. La consultation ponctuelle échantillonne un
-- COG côté serveur ; cette fonction lui dit lesquels : les actifs `cog` du
-- run le plus récent qui en possède — le run courant en temps normal, le
-- précédent pendant la minute où l'import a publié mais où la dérivation
-- n'a pas fini, ou le jour où elle a échoué. Servir hier en le datant vaut
-- mieux que ne rien dire ; c'est l'heure de validité, toujours renvoyée,
-- qui porte la vérité (FR-121).
--
-- Les chemins d'objets renvoyés vivent dans le compartiment public `tiles` :
-- rien ici n'ouvre un accès qui n'existait pas déjà par URL.
--
-- Idempotente (dette « migrations hors bande », plan §15) ; signature
-- qualifiée partout — la leçon des 42701/42725.
-- =============================================================================

create or replace function api.air_grid_assets()
returns table (
  pollutant text,
  unit text,
  resolution text,
  model text,
  run_at timestamptz,
  lead_hours integer,
  valid_at timestamptz,
  asset_path text,
  checksum text
)
language sql
stable
security definer
set search_path = air, pg_temp
as $$
  with chosen_run as (
    select r.id, r.model, r.run_at
    from air.model_runs r
    where exists (
      select 1 from air.grid_assets a
      where a.model_run_id = r.id and a.kind = 'cog'
    )
    order by r.is_current desc, r.run_at desc
    limit 1
  )
  select
    a.pollutant,
    a.unit,
    a.resolution,
    chosen_run.model,
    chosen_run.run_at,
    a.lead_hours,
    a.valid_at,
    a.asset_path,
    a.checksum
  from air.grid_assets a
  join chosen_run on chosen_run.id = a.model_run_id
  where a.kind = 'cog'
  order by a.pollutant, a.lead_hours;
$$;

comment on function api.air_grid_assets() is
  'Actifs COG du run de qualité de l''air le plus récent qui en possède, pour l''échantillonnage ponctuel serveur. Cahier §19.2, FR-121.';

grant execute on function api.air_grid_assets() to anon, authenticated;
