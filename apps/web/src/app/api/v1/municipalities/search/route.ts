import { municipalitySearchQuerySchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { createPublicServerClient } from '@/lib/supabase/server';

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

  const supabase = await createPublicServerClient();
  const { data, error } = await supabase.rpc('search_municipalities', {
    q: parsed.data.q,
    max_results: parsed.data.limit,
  });

  if (error !== null) {
    console.error('[api/municipalities/search] échec de la recherche', {
      requestId,
      code: error.code,
      message: error.message,
    });
    return jsonError(
      'INTERNAL_ERROR',
      'La recherche de commune est momentanément indisponible.',
      requestId,
    );
  }

  type Row = {
    insee_code: string;
    name: string;
    department_code: string;
    postal_codes: string[];
    longitude: number;
    latitude: number;
  };

  const results = ((data ?? []) as Row[]).map((row) => ({
    insee: row.insee_code,
    name: row.name,
    departmentCode: row.department_code,
    postalCodes: row.postal_codes,
    centroid: { type: 'Point' as const, coordinates: [row.longitude, row.latitude] as const },
  }));

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
