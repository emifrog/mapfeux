/**
 * Vocabulaires contrôlés du domaine MapFeux.
 *
 * Référence : cahier de développement v1.1, §17.4 et annexe D.
 *
 * Règle fondatrice : trois dimensions distinctes ne doivent jamais être
 * confondues — la fraîcheur technique, le niveau de vérification et
 * l'éventuel statut opérationnel officiel. Toute fusion de ces axes dans un
 * unique champ « statut » est un défaut de conception, pas une simplification.
 */

/**
 * Fraîcheur d'une source de données externe. Annexe D.
 *
 * `unavailable`, `maintenance` et `upcoming` décrivent trois situations que le
 * public ne doit pas confondre :
 *
 * - `unavailable` — la source est en service et n'a jamais rien livré. C'est
 *   une panne.
 * - `maintenance` — arrêtée volontairement, après avoir fonctionné.
 * - `upcoming` — déclarée au registre mais jamais mise en service : le
 *   connecteur n'existe pas encore. Ce n'est pas une panne, et la compter comme
 *   telle fait passer un service inachevé pour un service cassé (FR-150).
 */
export const SOURCE_FRESHNESS = [
  'fresh',
  'delayed',
  'stale',
  'unavailable',
  'maintenance',
  'upcoming',
] as const;
export type SourceFreshness = (typeof SOURCE_FRESHNESS)[number];

/**
 * Une source compte-t-elle dans le décompte affiché au public ?
 *
 * Le compteur d'en-tête répond à « le service fonctionne-t-il », pas à
 * « combien de sources le cahier prévoit-il ». Une source à venir ou en
 * maintenance n'entre donc ni au numérateur ni au dénominateur : la laisser au
 * dénominateur seul creuserait le ratio sans qu'aucune panne existe.
 */
export function isInService(freshness: SourceFreshness): boolean {
  return freshness !== 'upcoming' && freshness !== 'maintenance';
}

/**
 * Fraîcheur technique d'un événement : décrit uniquement l'ancienneté de la
 * dernière observation satellitaire. Ne conclut jamais sur l'extinction.
 */
export const EVENT_FRESHNESS = ['new', 'recent', 'not_recent', 'archived', 'hidden'] as const;
export type EventFreshness = (typeof EVENT_FRESHNESS)[number];

/**
 * Niveau de vérification de l'existence de l'événement.
 * L'ordre du tableau est significatif : il définit la progression normale.
 */
export const VERIFICATION_STATUS = [
  'satellite_detection',
  'probable_event',
  'publicly_reported',
  'officially_confirmed',
] as const;
export type VerificationStatus = (typeof VERIFICATION_STATUS)[number];

/**
 * Statut opérationnel officiel. Toujours nullable : il n'existe que s'il a été
 * publié par une autorité, avec source et horodatage attribués.
 */
export const OFFICIAL_CONTROL_STATUS = [
  'active',
  'contained',
  'controlled',
  'extinguished',
] as const;
export type OfficialControlStatus = (typeof OFFICIAL_CONTROL_STATUS)[number];

/** Nature de l'information exposée. Obligatoire sur tout bloc publié. */
export const PROVENANCE = [
  'observation',
  'algorithmic_inference',
  'model_estimate',
  'official_information',
  'editorial_correction',
  'external_report',
] as const;
export type Provenance = (typeof PROVENANCE)[number];

/**
 * Fiabilité publique d'un événement. Ne qualifie ni la gravité, ni la surface,
 * ni l'état opérationnel du feu.
 */
export const CONFIDENCE_LEVEL = ['low', 'medium', 'high'] as const;
export type ConfidenceLevel = (typeof CONFIDENCE_LEVEL)[number];

/** Type d'entrée de chronologie. §13.9. */
export const TIMELINE_ENTRY_TYPE = [
  'detection',
  'grouping',
  'smoke_forecast',
  'wind_change',
  'official_update',
  'editorial_correction',
  'status_change',
] as const;
export type TimelineEntryType = (typeof TIMELINE_ENTRY_TYPE)[number];

/** Visibilité d'une entrée de chronologie. Les retraits sont logiques. */
export const TIMELINE_VISIBILITY = ['public', 'internal', 'suppressed'] as const;
export type TimelineVisibility = (typeof TIMELINE_VISIBILITY)[number];

/** Type de territoire. §13.1. */
export const TERRITORY_TYPE = [
  'country',
  'region',
  'department',
  'collectivity',
  'custom',
] as const;
export type TerritoryType = (typeof TERRITORY_TYPE)[number];

export const TERRITORY_STATUS = ['draft', 'pilot', 'active', 'disabled'] as const;
export type TerritoryStatus = (typeof TERRITORY_STATUS)[number];

/** Auteur d'un changement journalisé. §13.8. */
export const ACTOR_TYPE = ['job', 'admin', 'system'] as const;
export type ActorType = (typeof ACTOR_TYPE)[number];

/** Rôles applicatifs. §14.1. */
export const ADMIN_ROLE = ['viewer_admin', 'content_admin', 'data_admin', 'super_admin'] as const;
export type AdminRole = (typeof ADMIN_ROLE)[number];
