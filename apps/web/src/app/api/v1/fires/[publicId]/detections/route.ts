import { publicEventIdSchema } from '@mapfeux/contracts';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchEvent, fetchEventDetections } from '@/lib/data/events';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/fires/{publicId}/detections — détections membres. Cahier §15.2.
 *
 * Les attributs bruts du fournisseur ne sont pas republiés tels quels : la
 * confiance VIIRS et la confiance MODIS n'ont pas le même sens, seul le niveau
 * normalisé sort. `raw_payload` n'est jamais exposé (ADR-004).
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ publicId: string }> },
): Promise<Response> {
  const requestId = newRequestId();
  const { publicId } = await context.params;

  const parsed = publicEventIdSchema.safeParse(publicId.toUpperCase());
  if (!parsed.success) {
    return jsonError('VALIDATION_ERROR', 'Identifiant d’événement invalide.', requestId);
  }

  const event = await fetchEvent(parsed.data);
  if (event === null) {
    return jsonError('NOT_FOUND', 'Cet événement n’est pas disponible.', requestId);
  }

  const [detections, sourceStatus] = await Promise.all([
    fetchEventDetections(parsed.data),
    fetchSourceStatus(),
  ]);

  return jsonSuccess(
    detections.map((detection) => ({
      acquiredAt: detection.acquiredAt.toISOString(),
      sensor: detection.sensor,
      satellite: detection.satellite,
      location: {
        type: 'Point' as const,
        coordinates: [detection.location.longitude, detection.location.latitude],
      },
      confidence: detection.confidenceLevel,
      frpMw: detection.frpMw,
      dayNight: detection.dayNight,
      isKnownThermalSource: detection.isKnownThermalSource,
    })),
    {
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: {
        generatedAt: new Date().toISOString(),
        sources: toMetaSources(sourceStatus.sources.filter((source) => source.key === 'firms')),
        disclaimer:
          'Un point correspond au centre approximatif d’un pixel satellite et non nécessairement au foyer exact.',
      },
    },
  );
}
