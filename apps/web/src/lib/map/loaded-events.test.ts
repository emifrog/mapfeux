import { describe, expect, it } from 'vitest';

import { toEventSummaries, type LoadedEventRow } from './loaded-events';

const ROW: LoadedEventRow = {
  id: 'MPF-9DVMRWBN',
  freshnessStatus: 'archived',
  verificationStatus: 'probable_event',
  officialControlStatus: null,
  firstDetectedAt: '2026-09-05T10:12:00.000Z',
  lastDetectedAt: '2026-09-06T02:41:00.000Z',
  location: { coordinates: [5.371107, 43.30457] },
  nearestMunicipality: { insee: '13039', name: 'Fos-sur-Mer' },
  detectionCount: 7,
  confidence: 'medium',
};

describe('toEventSummaries', () => {
  it('rend des dates, pas des chaînes', () => {
    // La liste calcule un âge et formate une heure : lui passer du texte
    // marcherait par coïncidence, jusqu'à la première soustraction.
    const [summary] = toEventSummaries([ROW]);
    expect(summary?.firstDetectedAt).toBeInstanceOf(Date);
    expect(summary?.lastDetectedAt.toISOString()).toBe('2026-09-06T02:41:00.000Z');
  });

  it('défait la géométrie GeoJSON en couple nommé', () => {
    // L'ordre de GeoJSON est longitude puis latitude — l'inverse de celui
    // qu'on prononce. C'est exactement là que les cartes se trompent.
    const [summary] = toEventSummaries([ROW]);
    expect(summary?.location).toEqual({ longitude: 5.371107, latitude: 43.30457 });
  });

  it('reprend le reste sans le déformer', () => {
    const [summary] = toEventSummaries([ROW]);
    expect(summary?.publicId).toBe('MPF-9DVMRWBN');
    expect(summary?.detectionCount).toBe(7);
    expect(summary?.confidenceLevel).toBe('medium');
    expect(summary?.nearestMunicipality).toEqual({ insee: '13039', name: 'Fos-sur-Mer' });
    expect(summary?.officialControlStatus).toBeNull();
  });

  it('garde l’ordre servi, qui est celui de la dernière observation', () => {
    const rows = [ROW, { ...ROW, id: 'MPF-AAAAAAAA' }, { ...ROW, id: 'MPF-BBBBBBBB' }];
    expect(toEventSummaries(rows).map((event) => event.publicId)).toEqual([
      'MPF-9DVMRWBN',
      'MPF-AAAAAAAA',
      'MPF-BBBBBBBB',
    ]);
  });

  it('une réponse vide donne une liste vide, jamais une exception', () => {
    expect(toEventSummaries([])).toEqual([]);
  });
});
