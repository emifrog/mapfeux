-- =============================================================================
-- Liste blanche des publications officielles captées — données de référence
--
-- ADR-026 : y entrer est un acte d'administration qui engage. N'y figurent
-- que des pages d'autorités sur les domaines de l'État, vérifiées à la
-- main avant l'ajout. Les territoires pilotes d'abord (06 et 83) ; les
-- autres départements viendront avec leur ouverture éditoriale, jamais en
-- masse.
--
-- `on conflict do nothing` : le seed n'écrase jamais un réglage
-- d'exploitation (désactivation comprise) posé en production.
-- =============================================================================

insert into app.official_feeds
  (organisation, feed_url, kind, department_code)
values
  (
    'Préfecture du Var',
    'https://www.var.gouv.fr/Actualites',
    'actualites_page',
    '83'
  ),
  (
    'Préfecture des Alpes-Maritimes',
    'https://www.alpes-maritimes.gouv.fr/Actualites',
    'actualites_page',
    '06'
  )
on conflict (feed_url) do nothing;
