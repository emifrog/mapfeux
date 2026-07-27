import { describe, expect, it } from 'vitest';

import { detectionContradictsOfficialStatus, evaluateStatusChange } from './status-transitions';
import type { EventStatusState } from './status-transitions';

const baseState: EventStatusState = {
  freshness: 'recent',
  verification: 'probable_event',
  officialControlStatus: null,
  officialStatusSourceId: null,
  officialStatusAt: null,
};

const admin = { type: 'admin', role: 'data_admin', id: 'a1b2c3' } as const;

describe('evaluateStatusChange — traitements automatiques', () => {
  it('autorise un job à regrouper une détection en événement probable', () => {
    const decision = evaluateStatusChange({
      actor: { type: 'job' },
      current: { ...baseState, verification: 'satellite_detection' },
      next: { verification: 'probable_event' },
      reason: 'regroupement algorithmique v1',
    });

    expect(decision.allowed).toBe(true);
    expect(decision.requiresAudit).toBe(true);
  });

  it('interdit à un job de confirmer officiellement un événement', () => {
    const decision = evaluateStatusChange({
      actor: { type: 'job' },
      current: baseState,
      next: { verification: 'officially_confirmed' },
      reason: 'détection persistante',
    });

    expect(decision.allowed).toBe(false);
    expect(decision.violations.map((v) => v.code)).toContain('JOB_CANNOT_SET_VERIFICATION');
  });

  it('interdit à un job de renseigner un statut opérationnel officiel', () => {
    const decision = evaluateStatusChange({
      actor: { type: 'job' },
      current: baseState,
      next: { officialControlStatus: 'extinguished' },
      reason: 'plus aucune détection',
    });

    expect(decision.allowed).toBe(false);
    expect(decision.violations.map((v) => v.code)).toContain('JOB_CANNOT_SET_OFFICIAL_STATUS');
  });
});

describe('evaluateStatusChange — attribution obligatoire', () => {
  it('refuse une confirmation officielle sans source ni date', () => {
    const decision = evaluateStatusChange({
      actor: admin,
      current: baseState,
      next: { verification: 'officially_confirmed' },
      reason: 'communiqué préfecture',
    });

    const codes = decision.violations.map((v) => v.code);
    expect(decision.allowed).toBe(false);
    expect(codes).toContain('MISSING_OFFICIAL_SOURCE');
    expect(codes).toContain('MISSING_OFFICIAL_TIMESTAMP');
  });

  it('accepte une confirmation officielle complètement attribuée', () => {
    const decision = evaluateStatusChange({
      actor: admin,
      current: baseState,
      next: {
        verification: 'officially_confirmed',
        officialStatusSourceId: 'src-prefecture-06',
        officialStatusAt: '2026-07-27T15:00:00Z',
      },
      reason: 'communiqué préfecture des Alpes-Maritimes',
    });

    expect(decision.violations).toEqual([]);
    expect(decision.allowed).toBe(true);
  });

  it('refuse un statut opérationnel sur un événement non confirmé', () => {
    const decision = evaluateStatusChange({
      actor: admin,
      current: baseState,
      next: {
        officialControlStatus: 'contained',
        officialStatusSourceId: 'src-sdis-06',
        officialStatusAt: '2026-07-27T18:00:00Z',
      },
      reason: 'point de situation SDIS',
    });

    expect(decision.allowed).toBe(false);
    expect(decision.violations.map((v) => v.code)).toContain(
      'OFFICIAL_STATUS_REQUIRES_CONFIRMATION',
    );
  });
});

describe('evaluateStatusChange — habilitations et traçabilité', () => {
  it('refuse un rôle insuffisant sur une information officielle', () => {
    const decision = evaluateStatusChange({
      actor: { type: 'admin', role: 'viewer_admin', id: 'v1' },
      current: baseState,
      next: {
        verification: 'officially_confirmed',
        officialStatusSourceId: 'src-prefecture-06',
        officialStatusAt: '2026-07-27T15:00:00Z',
      },
      reason: 'communiqué',
    });

    expect(decision.allowed).toBe(false);
    expect(decision.violations.map((v) => v.code)).toContain('INSUFFICIENT_ROLE');
  });

  it('exige un motif pour toute mutation de statut', () => {
    const decision = evaluateStatusChange({
      actor: admin,
      current: { ...baseState, verification: 'satellite_detection' },
      next: { verification: 'probable_event' },
    });

    expect(decision.allowed).toBe(false);
    expect(decision.violations.map((v) => v.code)).toContain('MISSING_REASON');
  });

  it('signale une régression du niveau de vérification', () => {
    const decision = evaluateStatusChange({
      actor: admin,
      current: { ...baseState, verification: 'publicly_reported' },
      next: { verification: 'probable_event' },
      reason: 'source externe rétractée',
    });

    expect(decision.allowed).toBe(true);
    expect(decision.isRegression).toBe(true);
  });

  it('ne demande pas d’audit lorsque rien de sensible ne change', () => {
    const decision = evaluateStatusChange({
      actor: { type: 'job' },
      current: baseState,
      next: { freshness: 'not_recent' },
    });

    expect(decision.allowed).toBe(true);
    expect(decision.requiresAudit).toBe(false);
  });
});

describe('detectionContradictsOfficialStatus', () => {
  it('signale une nouvelle détection sur un feu déclaré éteint', () => {
    expect(detectionContradictsOfficialStatus({ officialControlStatus: 'extinguished' })).toBe(
      true,
    );
  });

  it('ne signale rien sur un événement sans statut officiel', () => {
    expect(detectionContradictsOfficialStatus({ officialControlStatus: null })).toBe(false);
  });
});
