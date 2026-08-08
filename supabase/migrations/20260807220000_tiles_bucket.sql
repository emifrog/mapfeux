-- =============================================================================
-- 20260807220000 — Compartiment public des tuiles vectorielles
--
-- Cahier v2.1 §21.1 et §9.5 ; J3 « génération PMTiles ».
--
-- Créé par migration, comme les trois autres (leçon du 5 août : un compartiment
-- cliqué n'existe que sur le projet où on l'a cliqué).
--
-- `public: true`, et c'est le seul : un fichier PMTiles se lit par requêtes de
-- plage depuis le navigateur, sans jeton. Son contenu — limites administratives
-- simplifiées, déjà servies par l'API publique — est publiable par nature
-- (Licence Ouverte, attribution IGN/Etalab affichée sur la carte). Les données
-- brutes, elles, restent dans les compartiments privés.
--
-- L'écriture passe par la clé secrète serveur uniquement : aucune politique
-- d'écriture n'est ouverte, `public` ne concerne que la lecture.
-- =============================================================================

insert into storage.buckets (id, name, public)
values ('tiles', 'tiles', true)
on conflict (id) do update set public = true;
