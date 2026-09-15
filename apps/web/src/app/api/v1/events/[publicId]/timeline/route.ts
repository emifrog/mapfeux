import { publicEventIdSchema } from '@mapfeux/contracts';

import { jsonError, jsonSuccess, jsonUnavailable, newRequestId } from '@/lib/api/response';
import { fetchEvent, fetchEventTimeline } from '@/lib/data/events';

/**
 * GET /api/v1/events/{publicId}/timeline — chronologie publique. FR-055.
 *
 * Triée par heure de survenue, indépendamment de l'heure d'enregistrement. Les
 * entrées internes ou retirées ne sortent jamais de la base (§5.7).
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
  if (!event.readable) return jsonUnavailable(requestId);
  if (event.value === null) {
    return jsonError('NOT_FOUND', 'Cet événement n’est pas disponible.', requestId);
  }

  const entries = await fetchEventTimeline(parsed.data);
  if (!entries.readable) return jsonUnavailable(requestId);

  return jsonSuccess(
    entries.value.map((entry) => ({
      id: entry.id,
      entryType: entry.entryType,
      provenance: entry.provenance,
      occurredAt: entry.occurredAt.toISOString(),
      recordedAt: entry.recordedAt.toISOString(),
      title: entry.title,
      summary: entry.summary,
      source: entry.source,
    })),
    {
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: { generatedAt: new Date().toISOString(), sources: {} },
    },
  );
}
