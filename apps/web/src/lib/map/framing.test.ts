import { describe, expect, it } from 'vitest';

import { framingCenter } from './framing';

const EMPRISE: readonly [number, number] = [6.6, 43.6];

describe('framingCenter', () => {
  it('sans événement, c’est l’emprise qui est le sujet', () => {
    expect(framingCenter([], EMPRISE)).toEqual([6.6, 43.6]);
  });

  it('embrasse les deux extrêmes, pas la grappe la plus nombreuse', () => {
    // Relevé du 11 septembre 2026 : sept détections autour de Fos et d'Aix,
    // deux isolées plus à l'est. Une moyenne serait tirée par la grappe et
    // laisserait les isolées hors de l'écran.
    const points = [
      { longitude: 5.371, latitude: 43.305 },
      { longitude: 5.372, latitude: 43.303 },
      { longitude: 5.371, latitude: 43.305 },
      { longitude: 5.58, latitude: 43.651 },
      { longitude: 5.561, latitude: 43.647 },
      { longitude: 5.775, latitude: 43.549 },
      { longitude: 5.847, latitude: 43.475 },
      { longitude: 6.024, latitude: 44.018 },
      { longitude: 5.179, latitude: 43.547 },
    ];

    const [lon, lat] = framingCenter(points, EMPRISE);
    expect(lon).toBeCloseTo((5.179 + 6.024) / 2, 5);
    expect(lat).toBeCloseTo((43.303 + 44.018) / 2, 5);
  });

  it('un seul événement en devient le centre', () => {
    expect(framingCenter([{ longitude: 5.5, latitude: 43.2 }], EMPRISE)).toEqual([5.5, 43.2]);
  });

  it('écarte les coordonnées non finies plutôt que d’y perdre le cadrage', () => {
    const points = [
      { longitude: 5, latitude: 43 },
      { longitude: Number.NaN, latitude: 43.5 },
      { longitude: 6, latitude: 44 },
      { longitude: 5.5, latitude: Infinity },
    ];
    expect(framingCenter(points, EMPRISE)).toEqual([5.5, 43.5]);
  });

  it('rend l’emprise si aucun point n’est exploitable', () => {
    expect(framingCenter([{ longitude: Number.NaN, latitude: Number.NaN }], EMPRISE)).toEqual([
      6.6, 43.6,
    ]);
  });
});
