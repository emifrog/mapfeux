import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Une panne de lecture n'est pas une absence d'événements.
 *
 * Reproduit le constat d'audit du 15 septembre 2026 : PostgREST en erreur
 * rendait un tableau vide (catalogue, agrégats, détections) ou `null`
 * (fiche), et les pages en faisaient « 0 événement » et « introuvable ».
 * Le contrat testé est celui du `ReadResult` : l'erreur rend `readable:
 * false`, et seule une réponse **venue** de la base rend une valeur — y
 * compris vide.
 */

vi.mock('server-only', () => ({}));

const rpc = vi.fn();
vi.mock('@/lib/supabase/server', () => ({
  createPublicReadClient: () => ({ rpc }),
}));

const {
  fetchDepartmentAggregates,
  fetchEvent,
  fetchEventDetections,
  fetchEventObservationTimes,
  fetchEventsCatalog,
  fetchEventsNearMunicipality,
  fetchEventState,
  isEventOutsideTerritory,
  lookupEvent,
} = await import('./events');

const FAILURE = { data: null, error: { code: '57014', message: 'statement timeout' } };
const NOTHING = { data: [], error: null };

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  rpc.mockReset();
  vi.restoreAllMocks();
});

describe('la panne se dit, le vide se lit', () => {
  it('fiche : erreur → non lisible ; aucune ligne → lisible et nulle', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchEvent('MPF-AAAAAAAA')).toEqual({ readable: false });

    rpc.mockResolvedValueOnce(NOTHING);
    expect(await fetchEvent('MPF-AAAAAAAA')).toEqual({ readable: true, value: null });
  });

  it('catalogue : erreur → non lisible, jamais une première page vide', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchEventsCatalog()).toEqual({ readable: false });

    rpc.mockResolvedValueOnce(NOTHING);
    expect(await fetchEventsCatalog()).toEqual({
      readable: true,
      value: { events: [], nextCursor: null },
    });
  });

  it('agrégats départementaux : erreur → non lisible ; aucun → lisible et vide', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchDepartmentAggregates(new Date())).toEqual({ readable: false });

    rpc.mockResolvedValueOnce(NOTHING);
    expect(await fetchDepartmentAggregates(new Date())).toEqual({ readable: true, value: [] });
  });

  it('détections : erreur → non lisible', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchEventDetections('MPF-AAAAAAAA')).toEqual({ readable: false });
  });

  it('commune : la panne de l’emprise remonte, elle ne devient pas « aucun événement »', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    const result = await fetchEventsNearMunicipality({
      insee: '06004',
      centroid: { longitude: 7.12, latitude: 43.58 },
    });
    expect(result).toEqual({ readable: false });
  });

  it('périmètre : erreur → non lisible, ni « hors périmètre » ni « dedans »', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await isEventOutsideTerritory('MPF-AAAAAAAA')).toEqual({ readable: false });

    rpc.mockResolvedValueOnce({ data: true, error: null });
    expect(await isEventOutsideTerritory('MPF-AAAAAAAA')).toEqual({ readable: true, value: true });
  });
});

describe('l’état à un instant se lit en base, sans plafond', () => {
  const AT = new Date('2026-08-01T01:00:00Z');

  it('les observations sont demandées à l’instant, ou sans borne', async () => {
    rpc.mockResolvedValue(NOTHING);
    await fetchEventDetections('MPF-AAAAAAAA', 2000, { until: AT });
    expect(rpc).toHaveBeenLastCalledWith('fire_event_detections', {
      event_public_id: 'MPF-AAAAAAAA',
      max_results: 2000,
      until_at: AT.toISOString(),
    });
    await fetchEventDetections('MPF-AAAAAAAA');
    expect(rpc).toHaveBeenLastCalledWith('fire_event_detections', {
      event_public_id: 'MPF-AAAAAAAA',
      max_results: 500,
      until_at: null,
    });
  });

  it('état : la ligne d’agrégat se lit en nombres, les chaînes PostgREST comprises', async () => {
    rpc.mockResolvedValueOnce({
      data: [
        {
          observation_count: '2001',
          effective_at: '2026-08-01T01:00:00+00:00',
          sensors: ['MODIS', 'VIIRS'],
          frp_max_mw: '2197.4',
        },
      ],
      error: null,
    });
    expect(await fetchEventState('MPF-AAAAAAAA', AT)).toEqual({
      readable: true,
      value: {
        observationCount: 2001,
        effectiveAt: new Date('2026-08-01T01:00:00Z'),
        sensors: ['MODIS', 'VIIRS'],
        frpMaxMw: 2197.4,
      },
    });
    expect(rpc).toHaveBeenLastCalledWith('fire_event_state', {
      event_public_id: 'MPF-AAAAAAAA',
      until_at: AT.toISOString(),
    });
  });

  it('état : rien d’observé à cet instant est un zéro lu, une erreur ne l’est pas', async () => {
    rpc.mockResolvedValueOnce({
      data: [{ observation_count: 0, effective_at: null, sensors: [], frp_max_mw: null }],
      error: null,
    });
    expect(await fetchEventState('MPF-AAAAAAAA', AT)).toEqual({
      readable: true,
      value: { observationCount: 0, effectiveAt: null, sensors: [], frpMaxMw: null },
    });

    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchEventState('MPF-AAAAAAAA', AT)).toEqual({ readable: false });
  });

  it('instants d’observation : lus en dates et en nombres', async () => {
    rpc.mockResolvedValueOnce({
      data: [{ acquired_at: '2026-08-01T01:00:00+00:00', observation_count: '3' }],
      error: null,
    });
    expect(await fetchEventObservationTimes('MPF-AAAAAAAA')).toEqual({
      readable: true,
      value: [{ at: new Date('2026-08-01T01:00:00Z'), observationCount: 3 }],
    });
  });
});

describe('lookupEvent — événement, alias, rien, ou base muette', () => {
  it('base muette sur la fiche : non lisible, sans consulter les alias', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await lookupEvent('MPF-AAAAAAAA')).toEqual({ readable: false });
    expect(rpc).toHaveBeenCalledTimes(1);
  });

  it('base muette sur les alias : non lisible — pas un 404', async () => {
    rpc.mockResolvedValueOnce(NOTHING).mockResolvedValueOnce(FAILURE);
    expect(await lookupEvent('MPF-AAAAAAAA')).toEqual({ readable: false });
  });

  it('alias connu : redirection vers le canonique', async () => {
    rpc.mockResolvedValueOnce(NOTHING).mockResolvedValueOnce({ data: 'MPF-BBBBBBBB', error: null });
    expect(await lookupEvent('MPF-AAAAAAAA')).toEqual({
      readable: true,
      value: { kind: 'alias', canonical: 'MPF-BBBBBBBB' },
    });
  });

  it('inconnu des deux : manquant, et seulement alors', async () => {
    rpc.mockResolvedValueOnce(NOTHING).mockResolvedValueOnce({ data: null, error: null });
    expect(await lookupEvent('MPF-AAAAAAAA')).toEqual({
      readable: true,
      value: { kind: 'missing' },
    });
  });
});
