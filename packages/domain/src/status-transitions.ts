/**
 * Règles de transition des statuts d'événement.
 *
 * Référence : cahier §5.5 (FR-046, FR-047), §13.6 et §17.5.
 *
 * Ce module est la garde applicative qui empêche une détection satellitaire de
 * devenir une confirmation officielle par simple transition automatique. Il est
 * doublé par des contraintes en base : les deux doivent rester cohérents.
 */

import type {
  ActorType,
  AdminRole,
  EventFreshness,
  OfficialControlStatus,
  VerificationStatus,
} from './vocabulary';
import { OFFICIAL_CONTROL_STATUS, VERIFICATION_STATUS } from './vocabulary';

/** Niveaux de vérification qu'un traitement automatique a le droit d'écrire. */
const JOB_WRITABLE_VERIFICATION: readonly VerificationStatus[] = [
  'satellite_detection',
  'probable_event',
];

/** Rôles habilités à porter une information officielle sur un événement. */
const OFFICIAL_STATUS_ROLES: readonly AdminRole[] = ['data_admin', 'super_admin'];

export interface Actor {
  readonly type: ActorType;
  readonly role?: AdminRole;
  readonly id?: string;
}

export interface EventStatusState {
  readonly freshness: EventFreshness;
  readonly verification: VerificationStatus;
  readonly officialControlStatus: OfficialControlStatus | null;
  readonly officialStatusSourceId: string | null;
  readonly officialStatusAt: string | null;
}

export type StatusViolationCode =
  | 'JOB_CANNOT_SET_VERIFICATION'
  | 'JOB_CANNOT_SET_OFFICIAL_STATUS'
  | 'INSUFFICIENT_ROLE'
  | 'MISSING_ACTOR_IDENTITY'
  | 'MISSING_OFFICIAL_SOURCE'
  | 'MISSING_OFFICIAL_TIMESTAMP'
  | 'OFFICIAL_STATUS_REQUIRES_CONFIRMATION'
  | 'MISSING_REASON'
  | 'UNKNOWN_VALUE';

export interface StatusViolation {
  readonly code: StatusViolationCode;
  readonly message: string;
}

export interface StatusChangeRequest {
  readonly actor: Actor;
  readonly current: EventStatusState;
  readonly next: Partial<EventStatusState>;
  readonly reason?: string;
}

export interface StatusChangeDecision {
  readonly allowed: boolean;
  readonly violations: readonly StatusViolation[];
  /** Recul du niveau de vérification : autorisé mais toujours signalé. */
  readonly isRegression: boolean;
  /** Toute mutation de statut produit une entrée d'audit. §17.5. */
  readonly requiresAudit: boolean;
}

function verificationRank(status: VerificationStatus): number {
  return VERIFICATION_STATUS.indexOf(status);
}

/**
 * Évalue une demande de changement de statut sans l'appliquer.
 *
 * La fonction est pure et sans effet de bord : elle est appelée aussi bien par
 * l'API d'administration que par les tests de recette sur corpus historique.
 */
export function evaluateStatusChange(request: StatusChangeRequest): StatusChangeDecision {
  const { actor, current, next, reason } = request;
  const violations: StatusViolation[] = [];

  const verificationChanged =
    next.verification !== undefined && next.verification !== current.verification;
  const officialStatusChanged =
    next.officialControlStatus !== undefined &&
    next.officialControlStatus !== current.officialControlStatus;

  // --- Valeurs connues -------------------------------------------------------
  if (next.verification !== undefined && !VERIFICATION_STATUS.includes(next.verification)) {
    violations.push({
      code: 'UNKNOWN_VALUE',
      message: `Niveau de vérification inconnu : ${String(next.verification)}.`,
    });
  }
  if (
    next.officialControlStatus !== undefined &&
    next.officialControlStatus !== null &&
    !OFFICIAL_CONTROL_STATUS.includes(next.officialControlStatus)
  ) {
    violations.push({
      code: 'UNKNOWN_VALUE',
      message: `Statut officiel inconnu : ${String(next.officialControlStatus)}.`,
    });
  }

  // --- Traitements automatiques ---------------------------------------------
  // Un job ne modifie que la fraîcheur, le regroupement et la fiabilité.
  if (actor.type === 'job') {
    if (
      verificationChanged &&
      next.verification !== undefined &&
      !JOB_WRITABLE_VERIFICATION.includes(next.verification)
    ) {
      violations.push({
        code: 'JOB_CANNOT_SET_VERIFICATION',
        message:
          'Un traitement automatique ne peut pas déclarer un événement rapporté ou confirmé officiellement.',
      });
    }
    if (officialStatusChanged) {
      violations.push({
        code: 'JOB_CANNOT_SET_OFFICIAL_STATUS',
        message:
          'Un traitement automatique ne peut pas renseigner de statut opérationnel officiel.',
      });
    }
  }

  // --- Actions humaines ------------------------------------------------------
  const touchesOfficialLevel =
    officialStatusChanged ||
    (verificationChanged &&
      next.verification !== undefined &&
      !JOB_WRITABLE_VERIFICATION.includes(next.verification));

  if (actor.type === 'admin' && touchesOfficialLevel) {
    if (actor.id === undefined || actor.id.length === 0) {
      violations.push({
        code: 'MISSING_ACTOR_IDENTITY',
        message: "L'auteur doit être identifié pour porter une information officielle.",
      });
    }
    if (actor.role === undefined || !OFFICIAL_STATUS_ROLES.includes(actor.role)) {
      violations.push({
        code: 'INSUFFICIENT_ROLE',
        message: `Rôle insuffisant : ${OFFICIAL_STATUS_ROLES.join(' ou ')} requis.`,
      });
    }
  }

  if (
    (verificationChanged || officialStatusChanged) &&
    (reason === undefined || reason.trim() === '')
  ) {
    violations.push({
      code: 'MISSING_REASON',
      message: 'Toute mutation de statut exige un motif enregistré dans le journal d’audit.',
    });
  }

  // --- Attribution obligatoire ----------------------------------------------
  const resultingVerification = next.verification ?? current.verification;
  const resultingOfficialStatus =
    next.officialControlStatus !== undefined
      ? next.officialControlStatus
      : current.officialControlStatus;
  const resultingSourceId =
    next.officialStatusSourceId !== undefined
      ? next.officialStatusSourceId
      : current.officialStatusSourceId;
  const resultingStatusAt =
    next.officialStatusAt !== undefined ? next.officialStatusAt : current.officialStatusAt;

  const needsAttribution =
    resultingVerification === 'officially_confirmed' || resultingOfficialStatus !== null;

  if (needsAttribution) {
    if (resultingSourceId === null || resultingSourceId === '') {
      violations.push({
        code: 'MISSING_OFFICIAL_SOURCE',
        message: 'Une information officielle exige une source attribuée.',
      });
    }
    if (resultingStatusAt === null || resultingStatusAt === '') {
      violations.push({
        code: 'MISSING_OFFICIAL_TIMESTAMP',
        message: "Une information officielle exige la date de publication de l'autorité.",
      });
    }
  }

  // Un statut opérationnel officiel n'a de sens que sur un événement dont
  // l'existence est elle-même officiellement confirmée.
  if (resultingOfficialStatus !== null && resultingVerification !== 'officially_confirmed') {
    violations.push({
      code: 'OFFICIAL_STATUS_REQUIRES_CONFIRMATION',
      message:
        'Un statut opérationnel officiel suppose un événement officiellement confirmé au préalable.',
    });
  }

  const isRegression =
    verificationChanged &&
    next.verification !== undefined &&
    verificationRank(next.verification) < verificationRank(current.verification);

  return {
    allowed: violations.length === 0,
    violations,
    isRegression,
    requiresAudit: verificationChanged || officialStatusChanged,
  };
}

/**
 * Indique si une nouvelle observation satellitaire doit déclencher une revue de
 * cohérence plutôt qu'une modification silencieuse. §17.4.
 */
export function detectionContradictsOfficialStatus(
  state: Pick<EventStatusState, 'officialControlStatus'>,
): boolean {
  return (
    state.officialControlStatus === 'extinguished' || state.officialControlStatus === 'controlled'
  );
}
