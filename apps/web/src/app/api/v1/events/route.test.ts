import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * GET /api/v1/events : une base qui ne répond pas sort en 503 non caché.
 *
 * Constat d'audit du 15 septembre 2026, reproduit sur la route réelle : la
 * panne sortait en 200 avec `data: []`, `s-maxage=60` et
 * `stale-while-revalidate=300` — un faux vide gardé par le CDN et lu comme
 * « aucun événement en France ». Le vide **lu**, lui, reste un 200 cachable.
 */

vi.mock('server-only', () => ({}));

const fetchEventsCatalog = vi.fn();
const fetchEventsInBbox = vi.fn();
vi.mock('@/lib/data/events', () => ({
  fetchEventsCatalog,
  fetchEventsInBbox,
  decodeCatalogCursor: () => null,
}));
vi.mock('@/lib/sources', () => ({
  fetchSourceStatus: async () => ({ readable: true, sources: [] }),
  toMetaSources: () => ({}),
}));

const { GET } = await import('./route');

afterEach(() => {
  fetchEventsCatalog.mockReset();
  fetchEventsInBbox.mockReset();
});

describe('catalogue national', () => {
  it('base muette : 503 SOURCE_UNAVAILABLE, no-store, Retry-After', async () => {
    fetchEventsCatalog.mockResolvedValue({ readable: false });
    const response = await GET(new NextRequest('http://localhost/api/v1/events'));

    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('Retry-After')).toBe('60');
    const body = (await response.json()) as { error: { code: string } };
    expect(body.error.code).toBe('SOURCE_UNAVAILABLE');
  });

  it('catalogue vide, mais lu : 200 cachable et data: []', async () => {
    fetchEventsCatalog.mockResolvedValue({
      readable: true,
      value: { events: [], nextCursor: null },
    });
    const response = await GET(new NextRequest('http://localhost/api/v1/events'));

    expect(response.status).toBe(200);
    expect(response.headers.get('Cache-Control')).toContain('s-maxage=60');
    const body = (await response.json()) as { data: unknown[] };
    expect(body.data).toEqual([]);
  });
});

describe('événements par emprise', () => {
  it('base muette : 503, pas une emprise vide', async () => {
    fetchEventsInBbox.mockResolvedValue({ readable: false });
    const response = await GET(
      new NextRequest('http://localhost/api/v1/events?bbox=6.9,43.5,7.1,43.7'),
    );

    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
  });
});
