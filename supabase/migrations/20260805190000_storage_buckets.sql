-- =============================================================================
-- 20260805190000 — Compartiments de stockage objet
--
-- Cahier v2.1 §12.4 et annexe C ; ADR-025 (PR-1).
--
-- Les compartiments sont créés par migration, et non depuis le tableau de bord.
-- Un compartiment posé à la main n'existe que sur le projet où on l'a cliqué :
-- une base de recette, une base de calibration ou un projet reconstruit
-- repartiraient sans lui, et le dépôt échouerait sur « Bucket not found » —
-- exactement le symptôme observé le 5 août sur `archive-arome.py`.
--
-- Les trois sont **privés**. Ils portent de la donnée brute que le cahier
-- déclare immuable (ADR-004) et que §14.2 n'expose pas publiquement ; les
-- dépôts passent par la clé secrète côté serveur, qui traverse RLS.
-- =============================================================================

insert into storage.buckets (id, name, public)
values
  -- Fichiers bruts des fournisseurs, rétention 30 jours (§12.4). Ce qui y est
  -- déposé se retrouve auprès de la source si besoin.
  ('raw', 'raw', false),
  -- Produits dérivés : tuiles, agrégats, exports. Régénérables à partir de la
  -- base, donc sans valeur d'archive.
  ('derived', 'derived', false),
  -- Stockage froid PR-1. **Jamais purgé.**
  --
  -- L'exception de rétention est le point de ce compartiment, pas un détail de
  -- configuration. Ce qu'on y dépose — les extraits AROME — n'est pas
  -- retrouvable : Météo-France ne republie pas indéfiniment ses paquets, et un
  -- jour non capté est perdu définitivement. C'est ce qui fonde l'archivage
  -- (ADR-025).
  --
  -- Tout futur job de purge doit donc l'exclure **explicitement**, et non par
  -- omission : une purge écrite sur « tous les compartiments sauf ceux que je
  -- connais » détruirait des années de corpus le jour où quelqu'un la
  -- généralise. Risque « purge accidentelle du stockage froid PR-1 », §29.
  ('cold', 'cold', false)
on conflict (id) do nothing;
