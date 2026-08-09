import { publicEventIdSchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchEvent, fetchEventDetections, fetchEventTimeline } from '@/lib/data/events';

/**
 * GET /api/v1/events/{publicId}/state?at= — état reconstitué. Cahier §15.5.
 *
 * L'état est recomposé à la demande depuis les observations membres et la
 * chronologie (FR-086). La réponse distingue `requestedAt` — l'instant
 * demandé — d'`effectiveAt` — la dernière observation réellement disponible à
 * cet instant : entre les deux, rien n'a été observé, et la réponse le dit
 * plutôt que d'interpoler (FR-084).
 */
export async function GET(
  request: NextRequest,
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

  const rawAt = request.nextUrl.searchParams.get('at');
  const requestedAt = rawAt === null ? event.lastDetectedAt : new Date(rawAt);
  if (Number.isNaN(requestedAt.getTime())) {
    return jsonError('VALIDATION_ERROR', 'Paramètre at invalide, attendu ISO 8601.', requestId);
  }

  const [detections, timeline] = await Promise.all([
    fetchEventDetections(parsed.data, 2000),
    fetchEventTimeline(parsed.data),
  ]);

  const visible = detections.filter((d) => d.acquiredAt.getTime() <= requestedAt.getTime());
  const effectiveAt =
    visible.length > 0 ? new Date(Math.max(...visible.map((d) => d.acquiredAt.getTime()))) : null;

  return jsonSuccess(
    {
      id: event.publicId,
      requestedAt: requestedAt.toISOString(),
      effectiveAt: effectiveAt?.toISOString() ?? null,
      observationCount: visible.length,
      sensors: [...new Set(visible.map((d) => d.sensor))].sort(),
      frpMaxMw: visible.reduce<number | null>(
        (max, d) => (d.frpMw === null ? max : Math.max(max ?? 0, d.frpMw)),
        null,
      ),
      observations: visible.map((d) => ({
        acquiredAt: d.acquiredAt.toISOString(),
        location: {
          type: 'Point' as const,
          coordinates: [d.location.longitude, d.location.latitude],
        },
        sensor: d.sensor,
        confidence: d.confidenceLevel,
      })),
      timeline: timeline
        .filter((entry) => entry.occurredAt.getTime() <= requestedAt.getTime())
        .map((entry) => ({
          entryType: entry.entryType,
          provenance: entry.provenance,
          occurredAt: entry.occurredAt.toISOString(),
          title: entry.title,
        })),
    },
    {
      // Un état passé ne change que si un import tardif complète l'histoire :
      // cache plus long que les vues vivantes.
      sMaxAge: 300,
      staleWhileRevalidate: 3600,
      meta: {
        generatedAt: new Date().toISOString(),
        sources: {},
        disclaimer:
          'État reconstruit à partir des données connues et importées ; il ne représente pas nécessairement la situation réelle exacte de l’époque.',
      },
    },
  );
}
