import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * GET /api/v1/events/{publicId} : la panne n'est pas un 404.
 *
 * Constat d'audit du 15 septembre 2026 : une lecture manquée sortait en
 * 404 « Cet événement n'est pas disponible » — sur un identifiant qui
 * existe. Un consommateur aurait retenu que l'URL est morte (§13.10).
 */

vi.mock('server-only', () => ({}));

const lookupEvent = vi.fn();
const fetchEvent = vi.fn();
vi.mock('@/lib/data/events', () => ({ lookupEvent, fetchEvent }));
vi.mock('@/lib/sources', () => ({
  fetchSourceStatus: async () => ({ readable: true, sources: [] }),
  toMetaSources: () => ({}),
}));

const { GET } = await import('./route');

const context = { params: Promise.resolve({ publicId: 'MPF-AAAAAAAA' }) };

afterEach(() => {
  lookupEvent.mockReset();
  fetchEvent.mockReset();
});

describe('fiche événement', () => {
  it('base muette : 503 non caché, pas 404', async () => {
    lookupEvent.mockResolvedValue({ readable: false });
    const response = await GET(new Request('http://localhost/api/v1/events/MPF-AAAAAAAA'), context);

    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    const body = (await response.json()) as { error: { code: string } };
    expect(body.error.code).toBe('SOURCE_UNAVAILABLE');
  });

  it('identifiant inconnu, mais lu : 404', async () => {
    lookupEvent.mockResolvedValue({ readable: true, value: { kind: 'missing' } });
    const response = await GET(new Request('http://localhost/api/v1/events/MPF-AAAAAAAA'), context);

    expect(response.status).toBe(404);
  });

  it('alias vers un canonique illisible : 503, pas 404', async () => {
    lookupEvent.mockResolvedValue({
      readable: true,
      value: { kind: 'alias', canonical: 'MPF-BBBBBBBB' },
    });
    fetchEvent.mockResolvedValue({ readable: false });
    const response = await GET(new Request('http://localhost/api/v1/events/MPF-AAAAAAAA'), context);

    expect(response.status).toBe(503);
    expect(fetchEvent).toHaveBeenCalledWith('MPF-BBBBBBBB');
  });
});
