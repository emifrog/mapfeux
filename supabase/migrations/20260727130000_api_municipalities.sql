-- =============================================================================
-- 20260728090000 — Exposition publique des communes
--
-- Cahier §15.2 (`/municipalities/{insee}`) et §5.3.
--
-- Migration ajoutée plutôt que modification de `20260727120800_api_surface.sql`,
-- déjà appliquée : éditer un fichier de migration joué ferait diverger le
-- registre Supabase de son contenu réel.
--
-- La vue n'expose aucune géométrie. Les limites communales passent par les
-- tuiles vectorielles (§21.1) : les servir en JSON ferait plusieurs mégaoctets
-- par requête pour un rendu que MapLibre fait mieux.
-- =============================================================================

create view api.municipalities as
select
  m.insee_code,
  m.name,
  m.department_code,
  d.name as department_name,
  d.slug as department_slug,
  m.postal_codes,
  extensions.st_x(m.centroid) as longitude,
  extensions.st_y(m.centroid) as latitude,
  m.area_km2,
  m.source_version
from geo.municipalities m
left join app.territories d
  on d.type = 'department'
 and d.code = m.department_code
-- Seules les communes en vigueur. Les communes fusionnées restent en base pour
-- l'historique, mais ne sont plus proposées au public. §13.2
where m.valid_to is null;

comment on view api.municipalities is
  'Communes en vigueur, sans géométrie. Cahier §15.2.';

grant select on api.municipalities to anon, authenticated;

revoke insert, update, delete on api.municipalities from anon, authenticated;
