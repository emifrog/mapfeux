import { describe, expect, it } from 'vitest';

import { tierForZoom } from './zoom';

describe('tierForZoom', () => {
  it('n’expose que des agrégats départementaux en vue nationale', () => {
    const tier = tierForZoom(5);
    expect(tier.departmentAggregates).toBe(true);
    expect(tier.municipalities).toBe(false);
    expect(tier.rawDetections).toBe(false);
  });

  it('n’affiche les détections brutes qu’en vue locale', () => {
    expect(tierForZoom(12).rawDetections).toBe(false);
    expect(tierForZoom(13).rawDetections).toBe(true);
  });

  it('borne les zooms hors plage', () => {
    expect(tierForZoom(-3).departmentAggregates).toBe(true);
    expect(tierForZoom(99).rawDetections).toBe(true);
  });
});
