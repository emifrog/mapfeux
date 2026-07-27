import { resolveLocationBodySchema } from '@mapfeux/contracts';

import { jsonError, newRequestId } from '@/lib/api/response';
import { resolveMunicipality } from '@/lib/data/municipalities';

/**
 * POST /api/v1/location/resolve — commune contenant un point. FR-025.
 *
 * Confidentialité, cahier §22.2 :
 *
 * - la position arrive en corps de requête et non en paramètre d'URL, car les
 *   URL se retrouvent dans les journaux d'accès des CDN et des reverse proxies ;
 * - les coordonnées ne sont ni conservées, ni journalisées, y compris en cas
 *   d'erreur ;
 * - la réponse n'est jamais mise en cache : elle est propre à un utilisateur.
 */
export async function POST(request: Request): Promise<Response> {
  const requestId = newRequestId();

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError('VALIDATION_ERROR', 'Corps de requête illisible.', requestId);
  }

  const parsed = resolveLocationBodySchema.safeParse(body);
  if (!parsed.success) {
    return jsonError(
      'VALIDATION_ERROR',
      'Coordonnées invalides. Attendu : longitude et latitude en degrés décimaux.',
      requestId,
    );
  }

  let resolved;
  try {
    resolved = await resolveMunicipality(parsed.data.longitude, parsed.data.latitude);
  } catch {
    return jsonError(
      'INTERNAL_ERROR',
      'La localisation est momentanément indisponible. La recherche par nom reste utilisable.',
      requestId,
    );
  }

  if (resolved === null) {
    // Hors de France métropolitaine, ou en mer. Ce n'est pas une erreur.
    return jsonError(
      'NOT_FOUND',
      'Aucune commune ne correspond à cette position. Elle se situe peut-être hors du territoire couvert.',
      requestId,
    );
  }

  return Response.json(
    {
      data: resolved,
      meta: { generatedAt: new Date().toISOString(), sources: {} },
    },
    {
      status: 200,
      headers: {
        // Réponse propre à un utilisateur : jamais de cache partagé.
        'Cache-Control': 'no-store',
        'Content-Type': 'application/json; charset=utf-8',
      },
    },
  );
}
