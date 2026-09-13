import { describe, expect, it } from 'vitest';

import {
  AGE_BUCKETS_HOURS,
  CLUSTER_MAX_ZOOM,
  CLUSTER_RADIUS_EXPRESSION,
  FRESHNESS_COLOR_EXPRESSION,
  freshnessColorExpression,
  PALETTE,
} from './palette';

describe('freshnessColorExpression', () => {
  it('lit la propriété demandée et garde les seuils de la légende', () => {
    const grappe = freshnessColorExpression('minAge');
    expect(grappe[0]).toBe('step');
    expect(grappe[1]).toEqual(['get', 'minAge']);
    // Les mêmes paliers que la légende, dans le même ordre.
    expect(grappe[3]).toBe(AGE_BUCKETS_HOURS.new);
    expect(grappe[5]).toBe(AGE_BUCKETS_HOURS.recent);
    expect(grappe[7]).toBe(AGE_BUCKETS_HOURS.notRecent);
  });

  it('la version historique est celle des marqueurs, sur ageHours', () => {
    expect(FRESHNESS_COLOR_EXPRESSION[1]).toEqual(['get', 'ageHours']);
    expect(FRESHNESS_COLOR_EXPRESSION[2]).toBe(PALETTE.thermal.new);
    expect(FRESHNESS_COLOR_EXPRESSION.at(-1)).toBe(PALETTE.thermal.archived);
  });
});

describe('grappes', () => {
  it('cessent au zoom 9 : la carte de quartier n’a rien à regrouper (§21.3)', () => {
    expect(CLUSTER_MAX_ZOOM).toBe(8);
  });

  it('grossissent avec le compte, sans jamais rétrécir', () => {
    const rayons = [
      CLUSTER_RADIUS_EXPRESSION[2],
      CLUSTER_RADIUS_EXPRESSION[4],
      CLUSTER_RADIUS_EXPRESSION[6],
    ];
    expect(rayons).toEqual([...rayons].sort((a, b) => a - b));
  });
});
