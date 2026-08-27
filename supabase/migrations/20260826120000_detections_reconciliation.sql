-- =============================================================================
-- 20260826120000 — Enrichissement de réconciliation NRT/standard (J10)
--
-- Cahier v2.1 §16.3 et FR-032. Les détections NRT sont remplacées chez
-- FIRMS par les données scientifiques standard avec ~5 mois de décalage ;
-- la réconciliation rapproche l'archive standard des lignes déjà en base
-- et enregistre les corrections comme **enrichissements, jamais comme
-- réécritures** : `raw_payload` (le NRT reçu) reste immuable (ADR-004),
-- la ligne standard complète se range à côté.
--
-- `reconciled_at` est aussi le verrou d'idempotence : rejouer un trimestre
-- déjà traité ne met à jour aucune ligne — le critère de sortie de J10.
--
-- Aucun grant à poser : `mapfeux_ingest` a déjà `update` au niveau table.
-- Idempotente (dette « migrations hors bande », plan §15).
-- =============================================================================

alter table fire.detections
  add column if not exists standard_payload jsonb;

alter table fire.detections
  add column if not exists reconciled_at timestamptz;

comment on column fire.detections.standard_payload is
  'Ligne du produit standard FIRMS rapprochée par clé spatiotemporelle — l''enrichissement du §16.3, jamais une réécriture de raw_payload.';

comment on column fire.detections.reconciled_at is
  'Heure de la réconciliation NRT/standard. Non nul = ligne enrichie ; sert de verrou d''idempotence au rejeu.';
