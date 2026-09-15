import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * GET /api/v1/events/{publicId}/state : les chiffres viennent de la base,
 * la liste est plafonnée et le dit.
 *
 * Constat 3 de l'audit externe du 15 septembre 2026 : la route lisait les
 * 2 000 observations les plus récentes puis filtrait `at` en mémoire — avec
 * 2 001 observations, l'état à la première rendait zéro observation et
 * `effectiveAt` nul. Le contrat fixé ici : le compte, les capteurs, la FRP
 * maximale et `effectiveAt` sont ceux de `fetchEventState`, quel que soit le
 * contenu de la liste ; la liste est demandée **à l'instant** ; et une liste
 * plus courte que le compte est annoncée.
 */

vi.mock('server-only', () => ({}));

const fetchEvent = vi.fn();
const fetchEventState = vi.fn();
const fetchEventDetections = vi.fn();
const fetchEventTimeline = vi.fn();
vi.mock('@/lib/data/events', () => ({
  fetchEvent,
  fetchEventState,
  fetchEventDetections,
  fetchEventTimeline,
}));

const { GET } = await import('./route');

const context = { params: Promise.resolve({ publicId: 'MPF-AAAAAAAA' }) };
const FIRST = new Date('2026-08-01T01:00:00Z');
const LAST = new Date('2026-08-07T13:00:00Z');

function detection(at: Date, frpMw: number | null) {
  return {
    acquiredAt: at,
    sensor: 'VIIRS',
    satellite: 'N20',
    location: { longitude: 6.0, latitude: 43.5 },
    confidenceLevel: 'high',
    frpMw,
    dayNight: 'N',
    isKnownThermalSource: false,
  };
}

afterEach(() => {
  for (const mock of [fetchEvent, fetchEventState, fetchEventDetections, fetchEventTimeline]) {
    mock.mockReset();
  }
});

describe('état reconstitué', () => {
  it('lit la liste à l’instant demandé et prend ses chiffres de la base', async () => {
    fetchEvent.mockResolvedValue({
      readable: true,
      value: { publicId: 'MPF-AAAAAAAA', lastDetectedAt: LAST },
    });
    fetchEventState.mockResolvedValue({
      readable: true,
      value: {
        observationCount: 2001,
        effectiveAt: FIRST,
        sensors: ['MODIS', 'VIIRS'],
        frpMaxMw: 2197,
      },
    });
    // La liste ne porte qu'une observation : les chiffres ne doivent pas en
    // dépendre.
    fetchEventDetections.mockResolvedValue({ readable: true, value: [detection(FIRST, 12)] });
    fetchEventTimeline.mockResolvedValue({ readable: true, value: [] });

    const response = await GET(
      new NextRequest(
        `http://localhost/api/v1/events/MPF-AAAAAAAA/state?at=${FIRST.toISOString()}`,
      ),
      context,
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      data: {
        observationCount: number;
        effectiveAt: string;
        sensors: string[];
        frpMaxMw: number;
        observationLimit: number;
        observationsTruncated: boolean;
        observations: unknown[];
      };
    };

    expect(fetchEventState).toHaveBeenCalledWith('MPF-AAAAAAAA', FIRST);
    expect(fetchEventDetections).toHaveBeenCalledWith('MPF-AAAAAAAA', 2000, { until: FIRST });
    expect(body.data.observationCount).toBe(2001);
    expect(body.data.effectiveAt).toBe(FIRST.toISOString());
    expect(body.data.sensors).toEqual(['MODIS', 'VIIRS']);
    expect(body.data.frpMaxMw).toBe(2197);
    expect(body.data.observations).toHaveLength(1);
    expect(body.data.observationLimit).toBe(2000);
    expect(body.data.observationsTruncated).toBe(true);
  });

  it('une liste complète n’est pas annoncée partielle', async () => {
    fetchEvent.mockResolvedValue({
      readable: true,
      value: { publicId: 'MPF-AAAAAAAA', lastDetectedAt: LAST },
    });
    fetchEventState.mockResolvedValue({
      readable: true,
      value: { observationCount: 1, effectiveAt: FIRST, sensors: ['VIIRS'], frpMaxMw: 12 },
    });
    fetchEventDetections.mockResolvedValue({ readable: true, value: [detection(FIRST, 12)] });
    fetchEventTimeline.mockResolvedValue({ readable: true, value: [] });

    const response = await GET(
      new NextRequest('http://localhost/api/v1/events/MPF-AAAAAAAA/state'),
      context,
    );
    const body = (await response.json()) as { data: { observationsTruncated: boolean } };
    expect(body.data.observationsTruncated).toBe(false);
    // Sans `at`, l'instant est la dernière observation de l'événement.
    expect(fetchEventState).toHaveBeenCalledWith('MPF-AAAAAAAA', LAST);
  });

  it('état illisible : 503, jamais un état à zéro', async () => {
    fetchEvent.mockResolvedValue({
      readable: true,
      value: { publicId: 'MPF-AAAAAAAA', lastDetectedAt: LAST },
    });
    fetchEventState.mockResolvedValue({ readable: false });
    fetchEventDetections.mockResolvedValue({ readable: true, value: [] });
    fetchEventTimeline.mockResolvedValue({ readable: true, value: [] });

    const response = await GET(
      new NextRequest('http://localhost/api/v1/events/MPF-AAAAAAAA/state'),
      context,
    );
    expect(response.status).toBe(503);
  });
});
