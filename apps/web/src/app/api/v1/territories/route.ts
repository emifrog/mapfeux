import { jsonSuccess } from '@/lib/api/response';
import { fetchTerritories } from '@/lib/data/territories';

/**
 * GET /api/v1/territories — hiérarchie territoriale. Cahier §15.2, FR-010.
 *
 * Retourne les territoires ouverts ou pilotes. Ceux en préparation restent
 * invisibles : le filtre est porté par la vue `api.territories`, pas ici.
 */
export async function GET(): Promise<Response> {
  const territories = await fetchTerritories();

  return jsonSuccess(territories, {
    // La configuration territoriale change à la main, très rarement.
    sMaxAge: 3600,
    staleWhileRevalidate: 86_400,
    meta: {
      generatedAt: new Date().toISOString(),
      sources: {},
    },
  });
}
