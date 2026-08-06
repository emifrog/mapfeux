import { publicEventIdSchema } from '@mapfeux/contracts';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchEvent, resolveEventAlias } from '@/lib/data/events';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/events/{publicId} — fiche événement. Cahier §15.2 et §15.3.
 *
 * La réponse porte la provenance de chaque bloc : un consommateur de l'API doit
 * pouvoir distinguer une observation d'un calcul sans connaître notre
 * implémentation (§2.4).
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

  let event = await fetchEvent(parsed.data);

  if (event === null) {
    const canonical = await resolveEventAlias(parsed.data);
    if (canonical !== null && canonical !== parsed.data) {
      event = await fetchEvent(canonical);
    }
  }

  if (event === null) {
    return jsonError('NOT_FOUND', 'Cet événement n’est pas disponible.', requestId);
  }

  const sourceStatus = await fetchSourceStatus();
  const firms = sourceStatus.sources.filter((source) => source.key === 'firms');

  return jsonSuccess(
    {
      id: event.publicId,
      freshnessStatus: event.freshnessStatus,
      verificationStatus: event.verificationStatus,
      officialControlStatus: event.officialControlStatus,
      officialStatusSource: event.officialSource,
      firstDetectedAt: event.firstDetectedAt.toISOString(),
      lastDetectedAt: event.lastDetectedAt.toISOString(),
      location: {
        type: 'Point' as const,
        coordinates: [event.location.longitude, event.location.latitude],
      },
      nearestMunicipality: event.nearestMunicipality,
      territory: event.territory,
      detectionCount: event.detectionCount,
      sensors: event.sensors,
      satellites: event.satellites,
      confidence: event.confidenceLevel,
      frpMw: event.frp,
      provenance: {
        event: 'algorithmic_inference' as const,
        detections: 'observation' as const,
        ...(event.officialSource === null
          ? {}
          : { officialStatus: 'official_information' as const }),
      },
      timeline: {
        latestEntryAt: event.timelineLatestAt?.toISOString() ?? null,
        entryCount: event.timelineEntryCount,
      },
      // Reporté en v2 : un panache estimé au vent de surface est trop incertain
      // en relief pour être publié.
      smoke: null,
    },
    {
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: {
        generatedAt: new Date().toISOString(),
        lastKnownSnapshotAt: event.lastSnapshotAt?.toISOString() ?? null,
        sources: toMetaSources(firms),
        disclaimer:
          'Événement déduit de détections satellitaires, non équivalent à une confirmation officielle.',
      },
    },
  );
}
