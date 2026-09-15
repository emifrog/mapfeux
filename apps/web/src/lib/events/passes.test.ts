import { describe, expect, it } from 'vitest';

import { groupByPass, PASS_WINDOW_MS, type PassDetection } from './passes';

function pixel(
  iso: string,
  satellite: string,
  frpMw: number | null,
  dayNight: string | null = 'N',
): PassDetection {
  return {
    acquiredAt: new Date(iso),
    satellite,
    sensor: satellite.startsWith('N') ? 'VIIRS' : 'MODIS',
    frpMw,
    dayNight,
  };
}

describe('groupByPass', () => {
  it('fond les pixels d’un même satellite à la même minute en un passage', () => {
    const passes = groupByPass([
      pixel('2026-09-15T02:34:00Z', 'N20', 12.3),
      pixel('2026-09-15T02:34:00Z', 'N20', 4.5),
      pixel('2026-09-15T02:35:00Z', 'N20', 8),
    ]);
    expect(passes).toHaveLength(1);
    expect(passes[0]?.pixels).toBe(3);
    expect(passes[0]?.frpTotalMw).toBe(24.8);
    expect(passes[0]?.frpMaxMw).toBe(12.3);
    expect(passes[0]?.at.toISOString()).toBe('2026-09-15T02:34:00.000Z');
  });

  it('sépare deux satellites passés à la même minute', () => {
    const passes = groupByPass([
      pixel('2026-09-15T02:34:00Z', 'N20', 10),
      pixel('2026-09-15T02:34:00Z', 'N21', 20),
    ]);
    expect(passes.map((pass) => pass.satellite)).toEqual(['N20', 'N21']);
  });

  it('ouvre un nouveau passage au-delà de la fenêtre', () => {
    const start = new Date('2026-09-15T02:34:00Z').getTime();
    const passes = groupByPass([
      pixel(new Date(start).toISOString(), 'N20', 1),
      pixel(new Date(start + PASS_WINDOW_MS).toISOString(), 'N20', 1),
      pixel(new Date(start + PASS_WINDOW_MS + 60_000).toISOString(), 'N20', 1),
    ]);
    expect(passes).toHaveLength(2);
    expect(passes[0]?.pixels).toBe(2);
    expect(passes[1]?.pixels).toBe(1);
  });

  it('trie du plus ancien au plus récent quelle que soit l’entrée', () => {
    const passes = groupByPass([
      pixel('2026-09-15T12:00:00Z', 'N20', 1),
      pixel('2026-09-14T12:00:00Z', 'N21', 1),
      pixel('2026-09-15T03:00:00Z', 'N20', 1),
    ]);
    expect(passes.map((pass) => pass.at.toISOString())).toEqual([
      '2026-09-14T12:00:00.000Z',
      '2026-09-15T03:00:00.000Z',
      '2026-09-15T12:00:00.000Z',
    ]);
  });

  it('ne compte pas une puissance inconnue pour zéro', () => {
    const [known, unknown] = groupByPass([
      pixel('2026-09-15T02:34:00Z', 'N20', null),
      pixel('2026-09-15T02:34:00Z', 'N20', 7),
      pixel('2026-09-15T05:00:00Z', 'N20', null),
    ]);
    expect(known?.frpTotalMw).toBe(7);
    expect(known?.frpMaxMw).toBe(7);
    expect(unknown?.frpTotalMw).toBeNull();
    expect(unknown?.frpMaxMw).toBeNull();
    expect(unknown?.pixels).toBe(1);
  });

  it('tranche jour ou nuit à la majorité, et se tait sans indication', () => {
    const passes = groupByPass([
      pixel('2026-09-15T12:00:00Z', 'N20', 1, 'D'),
      pixel('2026-09-15T12:00:00Z', 'N20', 1, 'D'),
      pixel('2026-09-15T12:00:00Z', 'N20', 1, 'N'),
      pixel('2026-09-15T15:00:00Z', 'N20', 1, null),
    ]);
    expect(passes[0]?.dayNight).toBe('D');
    expect(passes[1]?.dayNight).toBeNull();
  });

  it('écarte une acquisition à date invalide', () => {
    const passes = groupByPass([
      pixel('pas une date', 'N20', 1),
      pixel('2026-09-15T12:00:00Z', 'N20', 1),
    ]);
    expect(passes).toHaveLength(1);
  });

  it('rend une liste vide sans observation', () => {
    expect(groupByPass([])).toEqual([]);
  });
});
