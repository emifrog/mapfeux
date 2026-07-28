import { bboxSchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchFiresInBbox } from '@/lib/data/events';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/fires — événements par emprise et période. Cahier §15.4.
 *
 * L'emprise est obligatoire. Sans elle, un appel unique ramènerait toute la
 * France : c'est précisément ce que FR-007 interdit, et ce qui s'effondrerait
 * au premier pic de trafic.
 */
export async function GET(request: NextRequest): Promise<Response> {
  const requestId = newRequestId();
  const params = request.nextUrl.searchParams;

  const rawBbox = params.get('bbox');
  if (rawBbox === null) {
    return jsonError(
      'INVALID_BBOX',
      'Paramètre bbox obligatoire, au format minLon,minLat,maxLon,maxLat.',
      requestId,
    );
  }

  const parsedBbox = bboxSchema.safeParse(rawBbox);
  if (!parsedBbox.success) {
    // Le schéma distingue une emprise malformée d'une emprise trop large : le
    // client doit savoir s'il doit corriger sa syntaxe ou zoomer.
    const code =
      parsedBbox.error.issues[0]?.message === 'BBOX_TOO_LARGE' ? 'BBOX_TOO_LARGE' : 'INVALID_BBOX';
    return jsonError(
      code,
      code === 'BBOX_TOO_LARGE'
        ? 'Emprise trop large pour cet endpoint. Rapprochez la vue.'
        : 'Emprise invalide.',
      requestId,
    );
  }

  const rawSince = params.get('since');
  const since = rawSince === null ? undefined : new Date(rawSince);
  if (since !== undefined && Number.isNaN(since.getTime())) {
    return jsonError('VALIDATION_ERROR', 'Paramètre since invalide, attendu ISO 8601.', requestId);
  }

  const rawLimit = params.get('limit');
  const limit = rawLimit === null ? 200 : Number.parseInt(rawLimit, 10);
  if (Number.isNaN(limit) || limit < 1) {
    return jsonError('VALIDATION_ERROR', 'Paramètre limit invalide.', requestId);
  }

  const events = await fetchFiresInBbox(parsedBbox.data, {
    ...(since === undefined ? {} : { since }),
    limit: Math.min(limit, 500),
  });

  const sourceStatus = await fetchSourceStatus();

  return jsonSuccess(
    events.map((event) => ({
      id: event.publicId,
      freshnessStatus: event.freshnessStatus,
      verificationStatus: event.verificationStatus,
      officialControlStatus: event.officialControlStatus,
      firstDetectedAt: event.firstDetectedAt.toISOString(),
      lastDetectedAt: event.lastDetectedAt.toISOString(),
      location: {
        type: 'Point' as const,
        coordinates: [event.location.longitude, event.location.latitude],
      },
      nearestMunicipality: event.nearestMunicipality,
      detectionCount: event.detectionCount,
      confidence: event.confidenceLevel,
    })),
    {
      // Court : la carte est le premier écran consulté pendant une crise.
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: {
        generatedAt: new Date().toISOString(),
        sources: toMetaSources(sourceStatus.sources.filter((s) => s.key === 'firms')),
        disclaimer:
          'Événements déduits de détections satellitaires, non équivalents à des confirmations officielles.',
      },
    },
  );
}
