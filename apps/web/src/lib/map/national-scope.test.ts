import { MAX_BBOX_AREA_DEG2 } from '@mapfeux/contracts';
import { describe, expect, it } from 'vitest';

import {
  bboxAreaDeg2,
  isWithinBboxCap,
  nationalSummary,
  scopeForZoom,
  toDepartmentRows,
  ZONE_MIN_ZOOM,
  type DepartmentAggregateInput,
} from './national-scope';

describe('scopeForZoom', () => {
  it('lit la France sous le seuil et une zone à partir de lui', () => {
    expect(scopeForZoom(5.2)).toBe('national');
    expect(scopeForZoom(ZONE_MIN_ZOOM - 0.01)).toBe('national');
    expect(scopeForZoom(ZONE_MIN_ZOOM)).toBe('zone');
    expect(scopeForZoom(13)).toBe('zone');
  });
});

describe('isWithinBboxCap', () => {
  it('mesure la surface et la compare au plafond de l’API', () => {
    expect(bboxAreaDeg2([5.2, 42.6, 8.0, 44.6])).toBeCloseTo(5.6, 5);
    expect(isWithinBboxCap([5.2, 42.6, 8.0, 44.6])).toBe(true);
    // La France métropolitaine : environ 150 degrés carrés.
    expect(isWithinBboxCap([-5.5, 41.2, 9.8, 51.2])).toBe(false);
    expect(bboxAreaDeg2([-5.5, 41.2, 9.8, 51.2])).toBeGreaterThan(MAX_BBOX_AREA_DEG2);
  });

  it('ne compte pas une emprise inversée comme une surface négative', () => {
    expect(bboxAreaDeg2([8, 44, 5, 42])).toBe(0);
  });
});

const AGGREGATES: DepartmentAggregateInput[] = [
  {
    departmentCode: '83',
    departmentSlug: 'var',
    departmentStatus: 'pilot',
    departmentName: 'Var',
    center: { longitude: 6.2, latitude: 43.5 },
    defaultZoom: 9,
    events: 12,
    substantiated: 4,
    lastDetectedAt: '2026-09-15T06:00:00Z',
  },
  {
    departmentCode: '59',
    departmentSlug: 'nord',
    departmentStatus: 'draft',
    departmentName: 'Nord',
    center: { longitude: 3.2, latitude: 50.5 },
    defaultZoom: 8,
    events: 57,
    substantiated: 20,
    lastDetectedAt: '2026-09-15T04:34:00Z',
  },
  {
    departmentCode: '2A',
    departmentSlug: 'corse-du-sud',
    departmentStatus: 'draft',
    departmentName: null,
    center: null,
    defaultZoom: null,
    events: 12,
    substantiated: 0,
    lastDetectedAt: '2026-09-14T22:00:00Z',
  },
];

describe('toDepartmentRows', () => {
  it('classe du plus au moins touché, puis par nom', () => {
    const rows = toDepartmentRows(AGGREGATES);
    expect(rows.map((row) => row.code)).toEqual(['59', '2A', '83']);
  });

  it('nomme, et sait où mener la carte ; une page seulement pour un département ouvert', () => {
    const [nord] = toDepartmentRows(AGGREGATES);
    expect(nord).toMatchObject({
      name: 'Nord',
      slug: 'nord',
      hasPage: false,
      center: [3.2, 50.5],
      zoom: 8,
    });
    expect(toDepartmentRows(AGGREGATES).find((row) => row.code === '83')?.hasPage).toBe(true);
  });

  it('garde un département sans nom, sous son code, sans destination', () => {
    const corse = toDepartmentRows(AGGREGATES).find((row) => row.code === '2A');
    expect(corse).toMatchObject({ name: '2A', center: null, zoom: null });
  });

  it('ne mène pas la carte sur un centre non fini', () => {
    const [row] = toDepartmentRows([
      { ...AGGREGATES[0]!, center: { longitude: Number.NaN, latitude: 43 } },
    ]);
    expect(row?.center).toBeNull();
  });
});

describe('nationalSummary', () => {
  it('totalise événements, étayés et départements concernés', () => {
    const rows = toDepartmentRows([
      ...AGGREGATES,
      { ...AGGREGATES[0]!, departmentCode: '06', events: 0, substantiated: 0 },
    ]);
    expect(nationalSummary(rows)).toEqual({ events: 81, substantiated: 24, departments: 3 });
  });
});
