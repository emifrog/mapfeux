import { publicEventIdSchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, jsonUnavailable, newRequestId } from '@/lib/api/response';
import {
  fetchEvent,
  fetchEventDetections,
  fetchEventState,
  fetchEventTimeline,
} from '@/lib/data/events';

/**
 * GET /api/v1/events/{publicId}/state?at= — état reconstitué. Cahier §15.5.
 *
 * L'état est recomposé à la demande depuis les observations membres et la
 * chronologie (FR-086). La réponse distingue `requestedAt` — l'instant
 * demandé — d'`effectiveAt` — la dernière observation réellement disponible à
 * cet instant : entre les deux, rien n'a été observé, et la réponse le dit
 * plutôt que d'interpoler (FR-084).
 *
 * Les chiffres — compte, capteurs, FRP maximale, `effectiveAt` — se calculent
 * **en base, sans plafond** ; la liste des observations est plafonnée à
 * `OBSERVATION_LIMIT` à l'instant demandé, et la réponse dit quand elle est
 * partielle. Jusqu'au 15 septembre 2026, la route lisait les 2 000
 * observations les plus récentes de toute la vie de l'événement puis filtrait
 * `at` en mémoire : avec 2 001 observations, l'état à la première rendait
 * zéro observation (constat 3 de l'audit externe).
 */

/** Le plafond de la fonction SQL, nommé pour être annoncé. */
const OBSERVATION_LIMIT = 2000;
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

  const read = await fetchEvent(parsed.data);
  if (!read.readable) return jsonUnavailable(requestId);
  const event = read.value;
  if (event === null) {
    return jsonError('NOT_FOUND', 'Cet événement n’est pas disponible.', requestId);
  }

  const rawAt = request.nextUrl.searchParams.get('at');
  const requestedAt = rawAt === null ? event.lastDetectedAt : new Date(rawAt);
  if (Number.isNaN(requestedAt.getTime())) {
    return jsonError('VALIDATION_ERROR', 'Paramètre at invalide, attendu ISO 8601.', requestId);
  }

  const [stateRead, detectionsRead, timelineRead] = await Promise.all([
    fetchEventState(parsed.data, requestedAt),
    fetchEventDetections(parsed.data, OBSERVATION_LIMIT, { until: requestedAt }),
    fetchEventTimeline(parsed.data),
  ]);
  // Un état reconstitué sur des observations non lues serait un état faux,
  // mis en cache cinq minutes : mieux vaut ne pas répondre.
  if (!stateRead.readable || !detectionsRead.readable || !timelineRead.readable) {
    return jsonUnavailable(requestId);
  }
  const state = stateRead.value;
  const visible = detectionsRead.value;
  const timeline = timelineRead.value;

  return jsonSuccess(
    {
      id: event.publicId,
      requestedAt: requestedAt.toISOString(),
      effectiveAt: state.effectiveAt?.toISOString() ?? null,
      observationCount: state.observationCount,
      sensors: state.sensors,
      frpMaxMw: state.frpMaxMw,
      // La liste est plafonnée, les chiffres ne le sont pas : quand elle est
      // partielle, la réponse le dit, et dit à combien elle s'arrête.
      observationLimit: OBSERVATION_LIMIT,
      observationsTruncated: state.observationCount > visible.length,
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
