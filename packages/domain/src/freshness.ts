/**
 * Calcul de la fraîcheur, côté domaine.
 *
 * Référence : cahier §5.13 (FR-111, FR-114), §21.5 et annexe D.
 *
 * Aucune donnée n'est présentée sans son âge. Une valeur issue du cache ou d'un
 * snapshot ancien doit être annoncée comme telle, jamais comme actuelle.
 */

import type { EventFreshness, SourceFreshness } from './vocabulary';

export const MINUTE_MS = 60_000;
export const HOUR_MS = 60 * MINUTE_MS;

/** Seuils par défaut de la fraîcheur d'un événement, en heures. */
export interface EventFreshnessThresholds {
  /** En deçà, l'événement est « nouveau ». */
  readonly newWithinHours: number;
  /** En deçà, l'observation est « récente ». */
  readonly recentWithinHours: number;
  /** Au-delà, l'événement sort de la fenêtre d'affichage courant. */
  readonly archivedAfterHours: number;
}

export const DEFAULT_EVENT_FRESHNESS_THRESHOLDS: EventFreshnessThresholds = {
  newWithinHours: 3,
  recentWithinHours: 24,
  archivedAfterHours: 7 * 24,
};

/**
 * Détermine la fraîcheur technique d'un événement.
 *
 * `not_recent` ne conclut jamais à une extinction : il indique seulement
 * l'absence de nouvelle observation satellitaire.
 */
export function computeEventFreshness(
  params: {
    readonly firstDetectedAt: Date;
    readonly lastDetectedAt: Date;
    readonly now: Date;
    readonly isHidden?: boolean;
  },
  thresholds: EventFreshnessThresholds = DEFAULT_EVENT_FRESHNESS_THRESHOLDS,
): EventFreshness {
  if (params.isHidden === true) return 'hidden';

  const ageSinceLast = params.now.getTime() - params.lastDetectedAt.getTime();
  const ageSinceFirst = params.now.getTime() - params.firstDetectedAt.getTime();

  if (ageSinceLast >= thresholds.archivedAfterHours * HOUR_MS) return 'archived';
  if (ageSinceFirst < thresholds.newWithinHours * HOUR_MS) return 'new';
  if (ageSinceLast < thresholds.recentWithinHours * HOUR_MS) return 'recent';
  return 'not_recent';
}

/**
 * Détermine la fraîcheur d'une source à partir de son intervalle attendu et de
 * son seuil de retard. §13.3.
 */
export function computeSourceFreshness(params: {
  readonly lastDataAt: Date | null;
  readonly now: Date;
  readonly staleAfterMs: number;
  readonly expectedIntervalMs: number;
  readonly isUnavailable?: boolean;
  readonly isMaintenance?: boolean;
}): SourceFreshness {
  if (params.isMaintenance === true) return 'maintenance';
  if (params.isUnavailable === true || params.lastDataAt === null) return 'unavailable';

  const age = params.now.getTime() - params.lastDataAt.getTime();
  if (age >= params.staleAfterMs) return 'stale';
  if (age >= params.expectedIntervalMs) return 'delayed';
  return 'fresh';
}

/**
 * Un snapshot doit-il être signalé comme ancien ? Cahier §21.5.
 *
 * La règle dépend de l'événement, pas seulement de l'horloge. Un snapshot
 * vieux de six heures est anormal sur un événement qui reçoit des observations
 * toutes les heures, et parfaitement normal sur un événement sans nouvelle
 * observation depuis trois jours. Signaler le second alarmerait sans motif et
 * apprendrait à l'utilisateur à ignorer la bannière.
 */
export function isSnapshotStale(params: {
  readonly generatedAt: Date;
  readonly now: Date;
  readonly eventFreshness: EventFreshness;
  readonly maxAgeMinutes?: number;
}): boolean {
  // Un événement sans observation récente n'a rien à recalculer : son snapshot
  // reste valide indéfiniment.
  if (params.eventFreshness !== 'new' && params.eventFreshness !== 'recent') {
    return false;
  }

  const maxAge = (params.maxAgeMinutes ?? 60) * MINUTE_MS;
  return params.now.getTime() - params.generatedAt.getTime() >= maxAge;
}

/** Âge d'une donnée en millisecondes, jamais négatif. */
export function dataAgeMs(dataAt: Date, now: Date): number {
  return Math.max(0, now.getTime() - dataAt.getTime());
}

/**
 * Formate un âge en français, pour affichage à côté de l'horodatage exact.
 * L'horodatage brut reste obligatoire : cette chaîne ne le remplace jamais.
 */
export function formatDataAge(ageMs: number): string {
  const minutes = Math.floor(ageMs / MINUTE_MS);
  if (minutes < 1) return "moins d'une minute";
  if (minutes < 60) return `${minutes} min`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) {
    return remainingMinutes === 0 ? `${hours} h` : `${hours} h ${remainingMinutes} min`;
  }

  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return remainingHours === 0 ? `${days} j` : `${days} j ${remainingHours} h`;
}
