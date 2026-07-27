-- =============================================================================
-- Territoires d'amorçage
--
-- Cahier §26.3 (jalon B : pilote 06 et 83) et §2.4 « multi-territoires natif ».
--
-- Les géométries ne sont pas renseignées ici : elles proviennent de l'import
-- IGN ADMIN EXPRESS (EPIC-02) et ne doivent pas être saisies à la main. Seuls
-- le centre de cadrage et le zoom par défaut sont configurés.
-- =============================================================================

insert into app.territories (type, code, slug, name, short_name, center, default_zoom, status)
values
  (
    'country', 'FR', 'france', 'France métropolitaine', 'France',
    extensions.st_setsrid(extensions.st_makepoint(2.55, 46.6), 4326), 5.2, 'active'
  )
on conflict (type, code) do nothing;

insert into app.territories
  (parent_id, type, code, slug, name, short_name, center, default_zoom, status)
select
  fr.id, 'region', '93', 'provence-alpes-cote-d-azur',
  'Provence-Alpes-Côte d''Azur', 'PACA',
  extensions.st_setsrid(extensions.st_makepoint(6.0, 43.9), 4326), 7.5, 'active'
from app.territories fr
where fr.type = 'country' and fr.code = 'FR'
on conflict (type, code) do nothing;

insert into app.territories
  (parent_id, type, code, slug, name, short_name, center, default_zoom, status)
select
  paca.id, 'department', '06', 'alpes-maritimes', 'Alpes-Maritimes', '06',
  extensions.st_setsrid(extensions.st_makepoint(7.10, 43.90), 4326), 9.0, 'pilot'
from app.territories paca
where paca.type = 'region' and paca.code = '93'
on conflict (type, code) do nothing;

insert into app.territories
  (parent_id, type, code, slug, name, short_name, center, default_zoom, status)
select
  paca.id, 'department', '83', 'var', 'Var', '83',
  extensions.st_setsrid(extensions.st_makepoint(6.25, 43.45), 4326), 9.0, 'pilot'
from app.territories paca
where paca.type = 'region' and paca.code = '93'
on conflict (type, code) do nothing;
