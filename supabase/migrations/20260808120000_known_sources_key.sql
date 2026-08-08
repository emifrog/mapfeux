-- =============================================================================
-- 20260808120000 — Clé d'idempotence des sources thermiques dérivées
--
-- Cahier §13.11 et FR-035 ; J10 « masque des sources statiques ».
--
-- Le référentiel initial est dérivé du corpus d'archives FIRMS 2012-2026 par
-- un calcul rejouable. Sans clé stable, chaque rejeu dupliquerait les sites ;
-- avec elle, le rejeu met à jour. Les entrées éditoriales — saisies à la main,
-- un volcan, une usine nommée — gardent une clé nulle : elles n'appartiennent
-- à aucune dérivation et aucun rejeu ne doit les toucher.
-- =============================================================================

alter table fire.known_thermal_sources
  add column source_key text unique;

comment on column fire.known_thermal_sources.source_key is
  'Clé stable de la dérivation (corpus). NULL pour une entrée éditoriale, '
  'intouchable par les rejeux.';
