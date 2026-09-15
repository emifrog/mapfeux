import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Territoires et liens officiels : la panne se dit, le vide se lit — même
 * patron que les événements (audit du 15 septembre 2026). L'accueil faisait
 * disparaître « Territoires ouverts » sur une base muette, et la page
 * territoire disait « aucun lien officiel » là où elle n'avait rien lu.
 */

vi.mock('server-only', () => ({}));

/** Un constructeur de requête Supabase : chaînable, puis attendable. */
let result: { data: unknown; error: unknown } = { data: [], error: null };
const maybeSingle = vi.fn(() => Promise.resolve(result));
vi.mock('@/lib/supabase/server', () => ({
  createPublicReadClient: () => ({
    from: () => {
      const chain = {
        select: () => chain,
        eq: () => chain,
        order: () => chain,
        maybeSingle,
        then: (onFulfilled: (value: typeof result) => unknown) =>
          Promise.resolve(result).then(onFulfilled),
      };
      return chain;
    },
  }),
}));

const { fetchOfficialLinks, fetchTerritories, fetchTerritory } = await import('./territories');

const FAILURE = { data: null, error: { code: '57014', message: 'statement timeout' } };

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  result = { data: [], error: null };
  vi.restoreAllMocks();
});

describe('territoires', () => {
  it('liste : erreur → non lisible ; aucune ligne → lisible et vide', async () => {
    result = FAILURE;
    expect(await fetchTerritories()).toEqual({ readable: false });

    result = { data: [], error: null };
    expect(await fetchTerritories()).toEqual({ readable: true, value: [] });
  });

  it('un territoire : erreur → non lisible ; inconnu → lisible et nul', async () => {
    result = FAILURE;
    expect(await fetchTerritory('var')).toEqual({ readable: false });

    result = { data: null, error: null };
    expect(await fetchTerritory('var')).toEqual({ readable: true, value: null });
  });

  it('liens officiels : erreur → non lisible, jamais « aucun lien »', async () => {
    result = FAILURE;
    expect(await fetchOfficialLinks('var')).toEqual({ readable: false });

    result = { data: [], error: null };
    expect(await fetchOfficialLinks('var')).toEqual({ readable: true, value: [] });
  });
});
