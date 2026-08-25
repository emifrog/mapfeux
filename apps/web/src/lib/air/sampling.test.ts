import { describe, expect, it } from 'vitest';

import { isStale, nearestCell, pickClosest, STALE_AFTER_MS } from './sampling';

/**
 * La grille CAMS réelle : bord nord-ouest (-5,8 ; 51,5), 0,1°, 160 × 105.
 * Les cas limites sont ceux qui mentiraient : bord exact, juste dehors.
 */
const CAMS_GRID = {
  originX: -5.8,
  originY: 51.5,
  resolutionX: 0.1,
  resolutionY: -0.1,
  width: 160,
  height: 105,
};

describe('pickClosest', () => {
  const at = (iso: string) => ({ validAt: new Date(iso) });

  it("choisit l'échéance la plus proche de l'instant demandé", () => {
    const assets = [
      at('2026-08-25T13:00:00Z'),
      at('2026-08-25T14:00:00Z'),
      at('2026-08-25T15:00:00Z'),
    ];
    const chosen = pickClosest(assets, new Date('2026-08-25T14:20:00Z'));
    expect(chosen?.validAt.toISOString()).toBe('2026-08-25T14:00:00.000Z');
  });

  it("retombe sur la dernière échéance quand l'instant dépasse le run", () => {
    const assets = [at('2026-08-25T23:00:00Z'), at('2026-08-26T00:00:00Z')];
    const chosen = pickClosest(assets, new Date('2026-08-26T07:00:00Z'));
    expect(chosen?.validAt.toISOString()).toBe('2026-08-26T00:00:00.000Z');
  });

  it('rend null sans actif', () => {
    expect(pickClosest([], new Date())).toBeNull();
  });
});

describe('isStale', () => {
  it("tolère le creux du matin — neuf heures avant l'import quotidien", () => {
    expect(isStale(new Date('2026-08-25T00:00:00Z'), new Date('2026-08-25T08:44:00Z'))).toBe(false);
  });

  it('déclare périmé un run entier manqué', () => {
    expect(isStale(new Date('2026-08-25T00:00:00Z'), new Date('2026-08-26T08:00:00Z'))).toBe(true);
  });

  it('la borne elle-même reste servie', () => {
    const validAt = new Date('2026-08-25T00:00:00Z');
    expect(isStale(validAt, new Date(validAt.getTime() + STALE_AFTER_MS))).toBe(false);
  });
});

describe('nearestCell', () => {
  it('Pontevès tombe dans la cellule attendue', () => {
    // (6,05 ; 43,55) : colonne (6,05 + 5,8) / 0,1 = 118, ligne (51,5 − 43,55) / 0,1 = 79.
    expect(nearestCell(CAMS_GRID, 6.05, 43.55)).toEqual({ column: 118, row: 79 });
  });

  it('le coin nord-ouest exact appartient à la première cellule', () => {
    expect(nearestCell(CAMS_GRID, -5.8, 51.5)).toEqual({ column: 0, row: 0 });
  });

  it("hors d'emprise rend null, jamais la cellule de bord", () => {
    expect(nearestCell(CAMS_GRID, -5.81, 45.0)).toBeNull();
    expect(nearestCell(CAMS_GRID, 10.21, 45.0)).toBeNull();
    expect(nearestCell(CAMS_GRID, 2.0, 40.99)).toBeNull();
    expect(nearestCell(CAMS_GRID, 2.0, 51.51)).toBeNull();
  });

  it('le bord sud-est exclu — il appartient à la grille voisine', () => {
    expect(nearestCell(CAMS_GRID, 10.2, 41.0)).toBeNull();
  });
});
