import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Communes : la panne se dit, le vide se lit — même patron que les
 * événements (audit du 15 septembre 2026). La page commune répondait 404 sur
 * une base muette, la recherche et la localisation levaient une exception que
 * la route traduisait en 500.
 */

vi.mock('server-only', () => ({}));

const rpc = vi.fn();
const maybeSingle = vi.fn();
vi.mock('@/lib/supabase/server', () => ({
  createPublicReadClient: () => ({
    rpc,
    from: () => {
      const chain = {
        select: () => chain,
        eq: () => chain,
        maybeSingle,
      };
      return chain;
    },
  }),
}));

const { fetchMunicipality, resolveMunicipality, searchMunicipalities } =
  await import('./municipalities');

const FAILURE = { data: null, error: { code: '57014', message: 'statement timeout' } };

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  rpc.mockReset();
  maybeSingle.mockReset();
  vi.restoreAllMocks();
});

describe('fetchMunicipality', () => {
  it('erreur → non lisible ; aucune ligne → lisible et nulle', async () => {
    maybeSingle.mockResolvedValueOnce(FAILURE);
    expect(await fetchMunicipality('06004')).toEqual({ readable: false });

    maybeSingle.mockResolvedValueOnce({ data: null, error: null });
    expect(await fetchMunicipality('06004')).toEqual({ readable: true, value: null });
  });
});

describe('searchMunicipalities et resolveMunicipality', () => {
  it('recherche : erreur → non lisible, sans exception ; rien → liste vide lue', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await searchMunicipalities('nice', 10)).toEqual({ readable: false });

    rpc.mockResolvedValueOnce({ data: [], error: null });
    expect(await searchMunicipalities('zzz', 10)).toEqual({ readable: true, value: [] });
  });

  it('localisation : erreur → non lisible ; hors de France → lisible et nulle', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await resolveMunicipality(7.0, 43.6)).toEqual({ readable: false });

    rpc.mockResolvedValueOnce({ data: [], error: null });
    expect(await resolveMunicipality(-30.0, 10.0)).toEqual({ readable: true, value: null });
  });
});
