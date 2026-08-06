-- =============================================================================
-- 20260806100000 — Vigilance : cadence et point d'accès temps réel
--
-- Cahier §9.2, §5.13 et FR-110.
--
-- Le registre décrivait une diffusion biquotidienne — périmée au-delà de vingt
-- heures — mais la source employée était le dépôt d'archive de data.gouv.fr.
-- Sondé le 6 août à 9 h UTC, il s'arrêtait au bulletin du 5 août 4 h : vingt-neuf
-- heures de retard. La vigilance affichait donc « trop ancienne » en permanence,
-- un signal exact et faux, qui apprend à ignorer l'indicateur.
--
-- L'ingestion passe à l'API temps réel de Météo-France. Les seuils décrivent
-- désormais la diffusion réelle du produit, non celle d'un miroir :
--
--   expected_interval  12 h  — diffusions nominales à 6 h et 16 h locales
--   stale_after        20 h  — au-delà, c'est une panne, pas une accalmie
--
-- Ces valeurs sont inchangées : elles étaient justes pour la source, fausses
-- pour la voie d'accès. Ce qui change est la voie.
--
-- `documentation_url` désignait le jeu « archivée », ce qui a masqué le
-- problème : le nom disait ce que le comportement révélait.
-- =============================================================================

update ingest.data_sources
set
  documentation_url = 'https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesVigilance',
  settings = settings
    || jsonb_build_object(
      'access', 'temps-reel',
      'endpoint', 'https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours',
      -- Quota annoncé par le portail. Une passe horaire en consomme une.
      'rate_limit_per_minute', 60,
      -- Repli sans clé, conservé et documenté pour ce qu'il vaut : environ un
      -- jour de retard. L'ingestion le signale alors explicitement.
      'fallback', 'depot-objet-data-gouv-archive',
      'fallback_lag_hours', 24
    )
where key = 'vigilance';
