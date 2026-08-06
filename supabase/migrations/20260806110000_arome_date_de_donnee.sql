-- =============================================================================
-- 20260806110000 — AROME : effacer les dates de donnée situées dans le futur
--
-- Cahier §5.13 et FR-110.
--
-- `archive-arome.py` renseignait `source_data_at` avec l'**échéance de la
-- prévision**, non l'heure de publication du run. La fraîcheur se calculant en
-- `now() - source_data_at`, la valeur devenait négative : /statut affichait
-- « il y a moins d'une minute » pour un horodatage à venir, et surtout la
-- détection de panne était neutralisée — AROME serait resté « à jour » des
-- heures après l'arrêt de l'archivage.
--
-- Le script est corrigé. Restent les passes déjà enregistrées, dont la valeur
-- future domine le `max()` de la vue et masque les passes correctes.
--
-- On efface plutôt qu'on ne rectifie. L'heure du run n'est pas récupérable
-- depuis ces lignes : elle n'y a jamais été écrite. Lui substituer l'heure
-- d'import serait inventer une précision qu'on n'a pas, alors que la vue sait
-- déjà quoi faire d'une date inconnue — `coalesce(source_data_at, finished_at)`,
-- posé par 20260728100000 précisément pour les sources qui ne datent pas leur
-- propre donnée.
--
-- Le critère est le défaut lui-même, non une liste d'identifiants : une date de
-- donnée postérieure à l'import qui l'a récupérée est impossible.
-- =============================================================================

update ingest.import_runs r
set source_data_at = null
from ingest.data_sources s
where s.id = r.source_id
  and s.key = 'arome'
  and r.source_data_at is not null
  and r.finished_at is not null
  and r.source_data_at > r.finished_at;
