import { describe, expect, it } from 'vitest';

import { hasOfficialStatusDivergence } from './coherence';

describe('hasOfficialStatusDivergence', () => {
  it('« éteint » puis observation postérieure : divergence', () => {
    expect(
      hasOfficialStatusDivergence({
        officialControlStatus: 'extinguished',
        officialStatusAt: '2026-08-20T10:00:00Z',
        lastDetectedAt: '2026-08-21T02:00:00Z',
      }),
    ).toBe(true);
  });

  it('« éteint » et aucune observation après : pas de divergence', () => {
    expect(
      hasOfficialStatusDivergence({
        officialControlStatus: 'extinguished',
        officialStatusAt: '2026-08-21T10:00:00Z',
        lastDetectedAt: '2026-08-21T02:00:00Z',
      }),
    ).toBe(false);
  });

  it('« maîtrisé » annonce la coexistence : jamais une divergence', () => {
    // Un feu maîtrisé émet encore de la chaleur — signaler une divergence
    // sur ce statut apprendrait à ignorer l'alerte.
    expect(
      hasOfficialStatusDivergence({
        officialControlStatus: 'controlled',
        officialStatusAt: '2026-08-20T10:00:00Z',
        lastDetectedAt: '2026-08-21T02:00:00Z',
      }),
    ).toBe(false);
  });

  it('sans statut officiel : rien à comparer', () => {
    expect(
      hasOfficialStatusDivergence({
        officialControlStatus: null,
        officialStatusAt: null,
        lastDetectedAt: '2026-08-21T02:00:00Z',
      }),
    ).toBe(false);
  });

  it("l'instant exact du statut n'est pas une divergence", () => {
    expect(
      hasOfficialStatusDivergence({
        officialControlStatus: 'extinguished',
        officialStatusAt: '2026-08-21T02:00:00Z',
        lastDetectedAt: '2026-08-21T02:00:00Z',
      }),
    ).toBe(false);
  });
});
