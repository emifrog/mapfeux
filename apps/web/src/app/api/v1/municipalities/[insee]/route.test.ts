import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * GET /api/v1/municipalities/{insee} : la panne n'est pas un 404.
 *
 * Même contrat que la fiche événement (audit du 15 septembre 2026) : une
 * base muette sort en 503 non caché ; seule une commune lue et inconnue sort
 * en 404 — un 404 sur une panne se mettrait en cache une heure.
 */

vi.mock('server-only', () => ({}));

const fetchMunicipality = vi.fn();
vi.mock('@/lib/data/municipalities', () => ({ fetchMunicipality }));
vi.mock('@/lib/sources', () => ({
  fetchSourceStatus: async () => ({ readable: true, sources: [] }),
  toMetaSources: () => ({}),
}));

const { GET } = await import('./route');

const context = { params: Promise.resolve({ insee: '06004' }) };

afterEach(() => {
  fetchMunicipality.mockReset();
});

describe('commune', () => {
  it('base muette : 503 non caché', async () => {
    fetchMunicipality.mockResolvedValue({ readable: false });
    const response = await GET(
      new Request('http://localhost/api/v1/municipalities/06004'),
      context,
    );

    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
  });

  it('commune inconnue, mais lue : 404', async () => {
    fetchMunicipality.mockResolvedValue({ readable: true, value: null });
    const response = await GET(
      new Request('http://localhost/api/v1/municipalities/06004'),
      context,
    );

    expect(response.status).toBe(404);
  });
});
