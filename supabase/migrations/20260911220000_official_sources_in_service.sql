-- =============================================================================
-- 20260911220000 — Mise en service de `prefectures` et `massifs`
--
-- Cahier v2.1 §8.1, FR-110 et FR-150. ADR-026 (liste blanche).
--
-- Les deux connecteurs ont été écrits en août et laissés **`disabled`** au
-- registre : le seed le dit mot pour mot, « reste `disabled` tant que le cron
-- n'a pas ses premières passes planifiées — passer à 'active' est le geste de
-- mise en service ». C'est ce geste.
--
-- Il est posé après contrôle, pas au calendrier. Relevé du 11 septembre 2026
-- au soir, sur les tâches réellement enregistrées :
--
--   massifs      69 passes, 68 complètes, 1 partielle, du 28/08 au 11/09
--   prefectures  100 passes, 95 complètes, 5 partielles, du 27/08 au 11/09
--
-- et de la donnée servie : 256 niveaux d'accès dans `app.massif_access_levels`,
-- 23 publications dans `app.official_feed_items`, deux flux en liste blanche.
-- Les cinq passes partielles de `prefectures` sont des sites préfectoraux
-- injoignables (`RemoteProtocolError` sur le 06 et le 83) — l'amont, pas le
-- connecteur, et le mode partiel est fait pour ça : ce qui a été lu est écrit,
-- ce qui manquait est nommé dans les métriques.
--
-- ## Ce que la bascule change, et ce qu'elle ne change pas
--
-- Rien à l'ingestion : les crons tournaient déjà, `status` ne les commande
-- pas. Ce qui change est **ce que le service dit de lui-même** — `freshness`
-- cessait d'être calculée pour ces deux sources (`maintenance` : arrêtée après
-- avoir fonctionné) et se mesure désormais sur l'âge de la donnée. Contrôlé
-- avant d'écrire, en rejouant le calcul de la vue sans rien modifier : les
-- deux ressortent `fresh` — massifs sur une donnée datée du lendemain, le
-- niveau étant publié la veille au soir ; prefectures sur une donnée de quatre
-- jours, pour un intervalle attendu de sept.
--
-- Le bandeau d'état et `/statut` suivent la vue, sans phrase d'attente à
-- retirer côté web : l'affichage « en maintenance » venait du statut au
-- registre et se résout avec lui — même constat qu'à la mise en service de
-- CAMS et du radar le 26 août.
--
-- Idempotente (dette « migrations hors bande », plan §15) : la clause `where`
-- rend le rejeu sans effet, et sur une base vierge les sources n'existent pas
-- encore — le seed les y pose directement `active`.
-- =============================================================================

update ingest.data_sources
set status = 'active',
    updated_at = now()
where key in ('prefectures', 'massifs')
  and status <> 'active';
