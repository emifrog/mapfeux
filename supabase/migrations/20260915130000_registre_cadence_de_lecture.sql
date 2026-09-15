-- =============================================================================
-- 20260915130000 — Le registre promet une cadence de lecture, pas de publication
--
-- Cahier v2.1 §5.13 (fausse assurance) et FR-110. Plan §15, dette « le registre
-- attend une cadence de donnée que la lecture ne promet pas ».
--
-- Relevé du 15 septembre 2026 à 10 h 04, sept tâches planifiées en `ok` aux
-- minutes près, et pourtant `/statut` lit trois sources en retard :
--
--   arome        « trop ancienne »  — la seule tâche est l'archive FWI, quotidienne
--                                     à 10 h 45 UTC ; le registre attendait 3 h
--   cams         « retardée »       — run de 00 h UTC daté de son run, lu à
--                                     08 h 45 UTC ; 24 h comptées depuis le run
--                                     précédent sont dépassées dès le petit matin
--   prefectures  « retardée »       — datée de la dernière **publication** trouvée
--                                     (huit jours), lue toutes les 15 minutes
--
-- Aucune panne derrière : trois promesses fausses. La vue `api.source_status`
-- mesure `now() - source_data_at` contre `expected_interval` ; ces intervalles
-- décrivent l'âge de la donnée que **notre chaîne** peut promettre — c'est déjà
-- la doctrine écrite pour le radar au seed —, donc la cadence de lecture plus le
-- délai entre l'instant dont la donnée est datée et l'instant où on la lit.
--
--   arome        run de 06 h UTC lu le lendemain à 10 h 45 UTC : 28 h 45,
--                plus le repli sur le run de 03 h si le plus frais manque
--                → 32 h ; trop ancienne à 56 h (deux lectures manquées)
--   cams         run de 00 h UTC lu le lendemain à 08 h 45 UTC : 32 h 45
--                → 34 h ; trop ancienne à 58 h
--   prefectures  lue toutes les 15 minutes, datée désormais de l'instant de
--                lecture (script `import-prefectures.py`, même jour) : la
--                borne d'une heure absorbe une passe manquée, six heures
--                disent que la chaîne ne lit plus — pas qu'une préfecture se
--                tait. Ce qu'elle a publié en dernier reste dans les
--                métriques de la passe et dans `app.official_feed_items`.
--
-- Idempotente : chaque `update` est sans effet une fois les bornes posées, et
-- sur une base vierge le seed pose directement ces valeurs.
-- =============================================================================

update ingest.data_sources
set expected_interval = interval '32 hours',
    stale_after = interval '56 hours',
    updated_at = now()
where key = 'arome'
  and (expected_interval <> interval '32 hours' or stale_after <> interval '56 hours');

update ingest.data_sources
set expected_interval = interval '34 hours',
    stale_after = interval '58 hours',
    updated_at = now()
where key = 'cams'
  and (expected_interval <> interval '34 hours' or stale_after <> interval '58 hours');

update ingest.data_sources
set expected_interval = interval '1 hour',
    stale_after = interval '6 hours',
    updated_at = now()
where key = 'prefectures'
  and (expected_interval <> interval '1 hour' or stale_after <> interval '6 hours');
