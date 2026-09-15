import { describe, expect, it } from 'vitest';

import { toFeatureCollection, type MapEvent } from './event-layer';

const NOW = new Date('2026-09-15T08:00:00Z');

const EVENT: MapEvent = {
  publicId: 'MPF-VHR8YJ85',
  freshnessStatus: 'new',
  lastDetectedAt: '2026-09-15T02:00:00Z',
  confidence: 'high',
  detectionCount: 57,
  location: { longitude: 3.811, latitude: 51.171 },
  nearestMunicipalityName: "Condé-sur-l'Escaut",
};

describe('toFeatureCollection', () => {
  it('calcule l’âge à la construction et garde l’horodatage pour le survol', () => {
    const [feature] = toFeatureCollection([EVENT], NOW).features;
    expect(feature?.properties?.['ageHours']).toBe(6);
    expect(feature?.properties?.['lastDetectedAt']).toBe('2026-09-15T02:00:00Z');
    expect(feature?.properties?.['kind']).toBeUndefined();
  });

  it('met à plat ce qu’une observation sait d’elle-même', () => {
    const [feature] = toFeatureCollection(
      [
        {
          ...EVENT,
          detectionCount: 1,
          observation: {
            sensor: 'VIIRS',
            satellite: 'N20',
            dayNight: 'N',
            frpMw: 12.3,
            confidence: 'unknown',
          },
        },
      ],
      NOW,
    ).features;
    expect(feature?.properties).toMatchObject({
      kind: 'observation',
      sensor: 'VIIRS',
      satellite: 'N20',
      dayNight: 'N',
      frpMw: 12.3,
      observationConfidence: 'unknown',
    });
  });

  it('ne fait pas voyager une valeur absente', () => {
    const [feature] = toFeatureCollection(
      [
        {
          ...EVENT,
          observation: {
            sensor: 'MODIS',
            satellite: 'Aqua',
            dayNight: null,
            frpMw: null,
            confidence: 'low',
          },
        },
      ],
      NOW,
    ).features;
    expect(feature?.properties).not.toHaveProperty('dayNight');
    expect(feature?.properties).not.toHaveProperty('frpMw');
  });
});
