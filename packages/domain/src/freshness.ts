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

/**
 * La donnée la plus récente **déjà là**, ou `null`.
 *
 * Symétrique d'`earliestUpcoming` : celle-ci écarte le passé, celle-là
 * écarte l'avenir.
 *
 * Une source peut horodater sa donnée en avance — le niveau d'accès aux
 * massifs du lendemain paraît la veille au soir. Retenue comme « la plus
 * récente », une telle donnée ferait dire au bandeau « maj il y a moins
 * d'une minute » en permanence, quoi qu'il arrive aux autres sources :
 * constaté le 11 septembre 2026, à la mise en service de `massifs`. C'est
 * la fausse assurance que le §5.13 interdit, et elle est d'autant plus
 * trompeuse qu'elle vient de la source la plus en avance, donc toujours
 * la même.
 *
 * Le connecteur a été corrigé pour dater ses passes de l'instant où il
 * lit ; cette fonction est la ceinture — aucune source, présente ou à
 * venir, ne peut plus faire dire au bandeau qu'il vient d'être à jour.
 */
export function mostRecentPast(dates: readonly (Date | null)[], now: Date): Date | null {
  let latest: Date | null = null;
  for (const date of dates) {
    if (date === null) continue;
    const time = date.getTime();
    if (Number.isNaN(time) || time > now.getTime()) continue;
    if (latest === null || time > latest.getTime()) latest = date;
  }
  return latest;
}

/**
 * « il y a 4 j 19 h », ou « dans 4 h 30 » quand l'horodatage est en avance.
 *
 * L'âge seul ne peut pas le dire : `dataAgeMs` ramène tout écart négatif à
 * zéro, qui se formate en « moins d'une minute » — un horodatage de demain
 * se lisait donc comme une donnée de l'instant.
 *
 * Une petite avance est tolérée sans commentaire : les horloges d'un
 * fournisseur et les nôtres ne sont pas synchronisées à la seconde, et
 * annoncer « dans 12 s » serait du bruit.
 */
export const CLOCK_TOLERANCE_MS = 2 * MINUTE_MS;

export function formatDataRecency(dataAt: Date, now: Date): string {
  const ahead = dataAt.getTime() - now.getTime();
  if (Number.isNaN(ahead)) return 'date inconnue';
  if (ahead > CLOCK_TOLERANCE_MS) return `dans ${formatDataAge(ahead)}`;
  return `il y a ${formatDataAge(dataAgeMs(dataAt, now))}`;
}

/**
 * La plus proche échéance **encore à venir**, ou `null`.
 *
 * Le bandeau d'état dit depuis quand la donnée date ; cette fonction lui
 * donne la suite — quand la prochaine est attendue. Par symétrie avec la
 * fraîcheur affichée, qui retient la donnée la plus récente de toutes les
 * sources en service, on retient ici l'échéance la plus proche : c'est le
 * moment où quelque chose bougera.
 *
 * Une échéance déjà passée est écartée plutôt que présentée comme un
 * retard : le retard se lit sur la pastille et sur /statut, et annoncer
 * « prochaine il y a deux heures » n'apprendrait rien à personne.
 */
export function earliestUpcoming(dates: readonly (Date | null)[], now: Date): Date | null {
  let earliest: Date | null = null;
  for (const date of dates) {
    if (date === null) continue;
    // Une date invalide franchit toutes les comparaisons, puisque `NaN` les
    // fait toutes échouer : sans ce test, `new Date(undefined)` — une colonne
    // absente de la réponse — devenait l'échéance retenue et faisait lever
    // `toISOString()`. Le build l'a attrapé sur /_not-found le 11 septembre.
    const time = date.getTime();
    if (Number.isNaN(time) || time <= now.getTime()) continue;
    if (earliest === null || time < earliest.getTime()) earliest = date;
  }
  return earliest;
}
