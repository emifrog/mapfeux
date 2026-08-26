import { afterEach, describe, expect, it, vi } from 'vitest';

/**
 * FR-125 : l'indisponibilité de CAMS ne bloque ni la fiche ni la page.
 *
 * Le contrat testé est celui de la panne : quelle que soit la façon dont la
 * chaîne casse — PostgREST en erreur, Storage injoignable, COG en 500 —
 * `fetchAirSamples` rend une liste vide, jamais une exception. C'est ce qui
 * garantit que la section de la fiche commune affiche sa branche d'absence
 * au lieu d'emporter la page.
 */

vi.mock('server-only', () => ({}));
vi.mock('@/lib/env', () => ({
  publicEnv: { NEXT_PUBLIC_SUPABASE_URL: 'https://storage.exemple.test' },
}));

const rpc = vi.fn();
vi.mock('@/lib/supabase/server', () => ({
  createPublicReadClient: () => ({ rpc }),
}));

const { fetchAirSamples } = await import('./air');

const NOW = new Date('2026-08-25T18:00:00Z');

const ASSET_ROW = {
  pollutant: 'pm10',
  unit: 'µg/m³',
  resolution: '0.1°',
  model: 'cams-europe-ensemble',
  run_at: '2026-08-25T00:00:00+00:00',
  lead_hours: 18,
  valid_at: '2026-08-25T18:00:00+00:00',
  asset_path: 'tiles/cams/pm10/20260825/cog-h18-deadbeefcafe.tif',
  checksum: 'deadbeefcafe' + '0'.repeat(52),
};

afterEach(() => {
  vi.unstubAllGlobals();
  rpc.mockReset();
});

describe('fetchAirSamples — FR-125, la panne rend vide, jamais une exception', () => {
  it('PostgREST en erreur : liste vide', async () => {
    rpc.mockResolvedValue({ data: null, error: { code: '500', message: 'cassé' } });
    await expect(fetchAirSamples(6.05, 43.55, NOW)).resolves.toEqual([]);
  });

  it('Storage injoignable : liste vide', async () => {
    rpc.mockResolvedValue({ data: [ASSET_ROW], error: null });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('réseau coupé')));
    await expect(fetchAirSamples(6.05, 43.55, NOW)).resolves.toEqual([]);
  });

  it('COG en 500 : liste vide', async () => {
    rpc.mockResolvedValue({ data: [ASSET_ROW], error: null });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })));
    await expect(fetchAirSamples(6.05, 43.55, NOW)).resolves.toEqual([]);
  });

  it("empreinte différente du registre : l'échantillon est écarté", async () => {
    rpc.mockResolvedValue({ data: [ASSET_ROW], error: null });
    // Un contenu quelconque : son SHA-256 ne peut pas être l'empreinte
    // enregistrée — la vérification doit écarter l'actif, pas le servir.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), { status: 200 })),
    );
    await expect(fetchAirSamples(6.05, 43.55, NOW)).resolves.toEqual([]);
  });
});
