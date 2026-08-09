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
--
-- `if not exists` : cette migration a été appliquée hors bande le 8 août
-- (calibration et production, par script), et le `db push` suivant l'a
-- rejouée — échec 42701 sur la version non idempotente. Règle tirée : toute
-- migration susceptible d'être appliquée par script avant le CLI doit être
-- écrite rejouable.
-- =============================================================================

alter table fire.known_thermal_sources
  add column if not exists source_key text unique;

comment on column fire.known_thermal_sources.source_key is
  'Clé stable de la dérivation (corpus). NULL pour une entrée éditoriale, '
  'intouchable par les rejeux.';
