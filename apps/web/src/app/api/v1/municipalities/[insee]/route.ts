import { inseeCodeSchema } from '@mapfeux/contracts';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchMunicipality } from '@/lib/data/municipalities';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/municipalities/{insee} — synthèse d'une commune. Cahier §15.2.
 *
 * Le code est validé avant d'atteindre la base : un identifiant malformé est
 * une erreur de l'appelant, pas une requête à exécuter.
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ insee: string }> },
): Promise<Response> {
  const requestId = newRequestId();
  const { insee } = await context.params;

  const parsed = inseeCodeSchema.safeParse(insee.toUpperCase());
  if (!parsed.success) {
    return jsonError(
      'VALIDATION_ERROR',
      'Code INSEE invalide. Il compte cinq caractères, par exemple 06088.',
      requestId,
    );
  }

  const municipality = await fetchMunicipality(parsed.data);
  if (municipality === null) {
    return jsonError('NOT_FOUND', 'Cette commune n’est pas disponible.', requestId);
  }

  // La fraîcheur est lue, jamais supposée. Une valeur codée en dur affirmerait
  // que la source est à jour sans l'avoir vérifié — §2.4.
  const sourceStatus = await fetchSourceStatus();
  const boundarySources = sourceStatus.sources.filter((s) => s.key === 'ign_admin_express');

  return jsonSuccess(municipality, {
    // Le référentiel communal ne bouge qu'aux mises à jour du COG.
    sMaxAge: 3600,
    staleWhileRevalidate: 86_400,
    meta: {
      generatedAt: new Date().toISOString(),
      sources: toMetaSources(boundarySources),
    },
  });
}
