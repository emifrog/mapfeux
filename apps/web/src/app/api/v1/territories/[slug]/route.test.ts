import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * GET /api/v1/territories/{slug} : la réponse porte les liens officiels ;
 * elle ne sort pas sans eux, et une base muette n'est pas un 404.
 */

vi.mock('server-only', () => ({}));

const fetchTerritory = vi.fn();
const fetchOfficialLinks = vi.fn();
vi.mock('@/lib/data/territories', () => ({ fetchTerritory, fetchOfficialLinks }));

const { GET } = await import('./route');

const context = { params: Promise.resolve({ slug: 'var' }) };
const TERRITORY = { slug: 'var', name: 'Var', type: 'department', code: '83' };

afterEach(() => {
  fetchTerritory.mockReset();
  fetchOfficialLinks.mockReset();
});

describe('territoire', () => {
  it('territoire illisible : 503, pas 404', async () => {
    fetchTerritory.mockResolvedValue({ readable: false });
    const response = await GET(new Request('http://localhost/api/v1/territories/var'), context);
    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
  });

  it('liens illisibles : 503 — une réponse sans liens dirait « aucun lien »', async () => {
    fetchTerritory.mockResolvedValue({ readable: true, value: TERRITORY });
    fetchOfficialLinks.mockResolvedValue({ readable: false });
    const response = await GET(new Request('http://localhost/api/v1/territories/var'), context);
    expect(response.status).toBe(503);
  });

  it('territoire inconnu, mais lu : 404', async () => {
    fetchTerritory.mockResolvedValue({ readable: true, value: null });
    const response = await GET(new Request('http://localhost/api/v1/territories/var'), context);
    expect(response.status).toBe(404);
  });

  it('tout lu : 200 avec les liens', async () => {
    fetchTerritory.mockResolvedValue({ readable: true, value: TERRITORY });
    fetchOfficialLinks.mockResolvedValue({ readable: true, value: [] });
    const response = await GET(new Request('http://localhost/api/v1/territories/var'), context);
    expect(response.status).toBe(200);
    const body = (await response.json()) as { data: { officialLinks: unknown[] } };
    expect(body.data.officialLinks).toEqual([]);
  });
});
