import { describe, expect, it } from 'vitest';

import { CHART_HEIGHT, CHART_WIDTH, frpChartModel, niceCeiling } from './frp-chart';
import type { SatellitePass } from './passes';

function pass(iso: string, frpTotalMw: number | null, pixels = 3): SatellitePass {
  return {
    at: new Date(iso),
    satellite: 'N20',
    sensor: 'VIIRS',
    pixels,
    frpTotalMw,
    frpMaxMw: frpTotalMw,
    dayNight: 'N',
  };
}

describe('niceCeiling', () => {
  it('arrondit au 1, 2 ou 5 supérieur', () => {
    expect(niceCeiling(137)).toBe(200);
    expect(niceCeiling(41)).toBe(50);
    expect(niceCeiling(7)).toBe(10);
    expect(niceCeiling(1.2)).toBe(2);
    expect(niceCeiling(50)).toBe(50);
  });

  it('ne rend jamais zéro ni un nombre non fini', () => {
    expect(niceCeiling(0)).toBe(1);
    expect(niceCeiling(Number.NaN)).toBe(1);
  });
});

describe('frpChartModel', () => {
  it('refuse de tracer une évolution avec moins de deux passages connus', () => {
    expect(frpChartModel([])).toBeNull();
    expect(frpChartModel([pass('2026-09-15T02:00:00Z', 12)])).toBeNull();
    expect(
      frpChartModel([pass('2026-09-15T02:00:00Z', 12), pass('2026-09-15T04:00:00Z', null)]),
    ).toBeNull();
  });

  it('part de zéro et plafonne à un nombre rond', () => {
    const model = frpChartModel([
      pass('2026-09-15T02:00:00Z', 30),
      pass('2026-09-15T04:00:00Z', 137),
    ]);
    expect(model?.maxMw).toBe(200);
    expect(model?.yTicks.map((tick) => tick.value)).toEqual([0, 100, 200]);
    expect(model?.yTicks.map((tick) => tick.y)).toEqual([CHART_HEIGHT, CHART_HEIGHT / 2, 0]);
    // 137 sur 200 : 68,5 % de la hauteur.
    expect(model?.bars[1]?.height).toBeCloseTo(68.5, 5);
    expect(model?.bars[1]?.y).toBeCloseTo(31.5, 5);
  });

  it('place les passages au temps, les barres extrêmes entières dans la boîte', () => {
    const model = frpChartModel([
      pass('2026-09-15T00:00:00Z', 10),
      pass('2026-09-15T06:00:00Z', 10),
      pass('2026-09-15T12:00:00Z', 10),
    ]);
    const [first, middle, last] = model?.bars ?? [];
    expect(first?.x).toBe(0);
    expect((last?.x ?? 0) + (last?.width ?? 0)).toBeCloseTo(CHART_WIDTH, 5);
    expect((middle?.x ?? 0) + (middle?.width ?? 0) / 2).toBeCloseTo(CHART_WIDTH / 2, 5);
  });

  it('marque au sol un passage sans puissance plutôt que de l’omettre', () => {
    const model = frpChartModel([
      pass('2026-09-15T00:00:00Z', 10),
      pass('2026-09-15T06:00:00Z', null),
      pass('2026-09-15T12:00:00Z', 10),
    ]);
    expect(model?.bars).toHaveLength(3);
    expect(model?.bars[1]).toMatchObject({ known: false, height: 0, y: CHART_HEIGHT });
  });

  it('resserre les barres quand les passages sont nombreux, sans descendre sous le visible', () => {
    const many = Array.from({ length: 400 }, (_, index) =>
      pass(new Date(Date.UTC(2026, 8, 1, 0, index * 10)).toISOString(), 5),
    );
    const model = frpChartModel(many);
    expect(model?.bars[0]?.width).toBe(4);
    const few = frpChartModel([pass('2026-09-15T00:00:00Z', 5), pass('2026-09-16T00:00:00Z', 5)]);
    expect(few?.bars[0]?.width).toBe(24);
  });

  it('borne l’axe du temps sur le premier et le dernier passage', () => {
    const model = frpChartModel([pass('2026-09-14T22:00:00Z', 1), pass('2026-09-15T02:00:00Z', 1)]);
    expect(model?.span.from.toISOString()).toBe('2026-09-14T22:00:00.000Z');
    expect(model?.span.to.toISOString()).toBe('2026-09-15T02:00:00.000Z');
  });
});
