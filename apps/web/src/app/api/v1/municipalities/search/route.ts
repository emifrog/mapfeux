import { municipalitySearchQuerySchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { searchMunicipalities } from '@/lib/data/municipalities';

/**
 * GET /api/v1/municipalities/search — recherche de commune. FR-020, FR-021.
 *
 * Le code INSEE est l'identifiant de référence ; le nom et le code postal ne
 * servent qu'à la recherche. Les homonymes se distinguent par le département.
 *
 * Cible de performance : p95 sous 300 ms (§6.2). La requête s'appuie sur
 * l'index trigramme de `geo.municipalities`.
 */
export async function GET(request: NextRequest): Promise<Response> {
  const requestId = newRequestId();

  const parsed = municipalitySearchQuerySchema.safeParse({
    q: request.nextUrl.searchParams.get('q') ?? '',
    limit: request.nextUrl.searchParams.get('limit') ?? undefined,
  });

  if (!parsed.success) {
    return jsonError(
      'VALIDATION_ERROR',
      'Paramètre de recherche invalide. Indiquez un nom de commune ou un code postal.',
      requestId,
    );
  }

  let results;
  try {
    results = await searchMunicipalities(parsed.data.q, parsed.data.limit);
  } catch {
    return jsonError(
      'INTERNAL_ERROR',
      'La recherche de commune est momentanément indisponible.',
      requestId,
    );
  }

  return jsonSuccess(results, {
    // Le référentiel communal ne change qu'aux mises à jour du COG.
    sMaxAge: 3600,
    staleWhileRevalidate: 86_400,
    meta: {
      generatedAt: new Date().toISOString(),
      sources: {},
    },
  });
}
