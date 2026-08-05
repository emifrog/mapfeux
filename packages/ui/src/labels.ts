/**
 * Libellés publics des vocabulaires contrôlés.
 *
 * Référence : cahier §2.4 « prudence sémantique ».
 *
 * Ces formulations sont validées métier. Elles évitent « incendie confirmé »,
 * « feu actif » ou « feu éteint » lorsqu'aucune source officielle n'est
 * attribuée. Aucun composant ne doit produire sa propre traduction.
 */

import type {
  ConfidenceLevel,
  EventFreshness,
  OfficialControlStatus,
  Provenance,
  SourceFreshness,
  VerificationStatus,
} from '@mapfeux/domain';

export const EVENT_FRESHNESS_LABELS: Record<EventFreshness, string> = {
  new: 'Nouvelle détection',
  recent: 'Observation récente',
  not_recent: 'Pas de nouvelle observation',
  archived: 'Archivé',
  hidden: 'Masqué',
};

/** Description longue, utilisée en infobulle et par les lecteurs d'écran. */
export const EVENT_FRESHNESS_DESCRIPTIONS: Record<EventFreshness, string> = {
  new: 'Événement créé récemment à partir de détections satellitaires.',
  recent: 'Une observation satellitaire a été enregistrée dans les dernières 24 heures.',
  not_recent:
    "Aucune nouvelle observation satellitaire récente. Cela n'indique pas que le phénomène est terminé.",
  archived: "Événement sorti de la fenêtre d'affichage courante.",
  hidden: 'Événement retiré de la carte publique par un administrateur.',
};

export const VERIFICATION_STATUS_LABELS: Record<VerificationStatus, string> = {
  satellite_detection: 'Détection thermique',
  probable_event: 'Événement probable',
  publicly_reported: 'Rapporté publiquement',
  officially_confirmed: 'Confirmé officiellement',
};

export const VERIFICATION_STATUS_DESCRIPTIONS: Record<VerificationStatus, string> = {
  satellite_detection:
    'Une ou plusieurs anomalies thermiques observées par satellite, sans regroupement robuste.',
  probable_event: 'Regroupement algorithmique cohérent de plusieurs détections.',
  publicly_reported: 'Événement mentionné par une source externe identifiable, non officielle.',
  officially_confirmed: 'Information publiée par une autorité et attribuée dans la base.',
};

export const OFFICIAL_CONTROL_STATUS_LABELS: Record<OfficialControlStatus, string> = {
  active: 'Feu en cours',
  contained: 'Feu fixé',
  controlled: 'Feu maîtrisé',
  extinguished: 'Feu éteint',
};

export const PROVENANCE_LABELS: Record<Provenance, string> = {
  observation: 'Observation',
  algorithmic_inference: 'Calcul automatique',
  model_estimate: 'Estimation de modèle',
  official_information: 'Information officielle',
  editorial_correction: 'Correction éditoriale',
  external_report: 'Source externe',
};

export const CONFIDENCE_LEVEL_LABELS: Record<ConfidenceLevel, string> = {
  low: 'Faible',
  medium: 'Modérée',
  high: 'Élevée',
};

/**
 * Précision obligatoire à côté du niveau de fiabilité.
 * Cahier §5.5, FR-049 : il ne qualifie ni la gravité, ni la surface, ni l'état
 * opérationnel du feu. Sans cette phrase, « fiabilité élevée » se lit comme
 * « feu important ».
 */
export const CONFIDENCE_LEVEL_NOTICE =
  'La fiabilité qualifie la cohérence des observations satellitaires. Elle ne dit rien de la gravité, de la surface ni de l’état du phénomène.';

export const SOURCE_FRESHNESS_LABELS: Record<SourceFreshness, string> = {
  fresh: 'À jour',
  delayed: 'Retardée',
  stale: 'Trop ancienne',
  unavailable: 'Indisponible',
  maintenance: 'Maintenance',
  // Déclarée au registre, connecteur pas encore écrit. « Indisponible »
  // annonçait une panne pour ce qui n'est qu'un chantier à venir.
  upcoming: 'À venir',
};
