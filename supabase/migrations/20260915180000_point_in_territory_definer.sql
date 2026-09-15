-- =============================================================================
-- 20260915180000 — Le déclencheur de périmètre ne dépend pas des droits de qui écrit
--
-- ADR-027, plan §15 (« le poste Windows ingère sous le rôle postgres »).
--
-- Trouvé en préparant la bascule du poste sur `mapfeux_ingest`, le
-- 15 septembre 2026 : ce rôle n'a aucun droit sur `app.territories` — il n'en
-- avait pas besoin, aucune passe ne lit les territoires. Or le déclencheur
-- `events_enforce_territory` (49ᵉ migration) appelle `fire.point_in_territory`
-- sous le rôle qui écrit, et cette fonction lit `app.territories` : sous
-- `mapfeux_ingest`, chaque insertion ou mise à jour d'événement aurait échoué
-- en « permission denied » — le regroupement entier, à la première passe.
-- Sous `postgres`, le poste ne l'a jamais vu.
--
-- La règle du périmètre est une propriété du service, pas un droit de
-- lecture à distribuer : la fonction passe en `security definer`, avec un
-- `search_path` fixé, et lit les territoires en tant que propriétaire. Le
-- rôle d'ingestion garde ses vingt tables et rien de plus.
--
-- Même signature, `create or replace` : idempotente et rejouable.
-- =============================================================================

create or replace function fire.point_in_territory(point extensions.geometry)
returns boolean
language sql
stable
security definer
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
  'littoral. La règle du périmètre du service, en un seul endroit ; lit les '
  'territoires en tant que propriétaire pour que le déclencheur tienne sous '
  'n''importe quel rôle d''écriture. ADR-027.';

grant execute on function fire.point_in_territory(extensions.geometry) to mapfeux_ingest;
