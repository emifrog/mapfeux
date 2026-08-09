import { bboxSchema } from '@mapfeux/contracts';
import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { decodeCatalogCursor, fetchEventsCatalog, fetchEventsInBbox } from '@/lib/data/events';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/events — événements par emprise, ou catalogue national. §15.4.
 *
 * Deux régimes, un seul endpoint (cahier §15.2) :
 *
 * - avec `bbox` : les événements de l'emprise, pour la carte (FR-007) ;
 * - sans `bbox` : le **catalogue national** (FR-050), borné par une
 *   pagination par jeu de clés — jamais par une emprise France entière, qui
 *   s'effondrerait au premier pic de trafic, ni par un offset.
 */

const VERIFICATION_VALUES = new Set([
  'satellite_detection',
  'probable_event',
  'publicly_reported',
  'officially_confirmed',
]);

const DEPARTMENT_PATTERN = /^(\d{2}|2[ab])$/i;

export async function GET(request: NextRequest): Promise<Response> {
  const requestId = newRequestId();
  const params = request.nextUrl.searchParams;

  const rawBbox = params.get('bbox');
  if (rawBbox === null) {
    return catalog(params, requestId);
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

  const events = await fetchEventsInBbox(parsedBbox.data, {
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

/** Catalogue national : filtres §15.4, curseur opaque, limite plafonnée. */
async function catalog(params: URLSearchParams, requestId: string): Promise<Response> {
  const rawSince = params.get('since');
  const since = rawSince === null ? undefined : new Date(rawSince);
  if (since !== undefined && Number.isNaN(since.getTime())) {
    return jsonError('VALIDATION_ERROR', 'Paramètre since invalide, attendu ISO 8601.', requestId);
  }

  const rawUntil = params.get('until');
  const until = rawUntil === null ? undefined : new Date(rawUntil);
  if (until !== undefined && Number.isNaN(until.getTime())) {
    return jsonError('VALIDATION_ERROR', 'Paramètre until invalide, attendu ISO 8601.', requestId);
  }

  const rawDepartment = params.get('department');
  if (rawDepartment !== null && !DEPARTMENT_PATTERN.test(rawDepartment)) {
    return jsonError(
      'VALIDATION_ERROR',
      'Paramètre department invalide : code sur deux caractères (01 à 95, 2A, 2B).',
      requestId,
    );
  }

  const rawVerification = params.get('verification');
  if (rawVerification !== null && !VERIFICATION_VALUES.has(rawVerification)) {
    return jsonError('VALIDATION_ERROR', 'Paramètre verification inconnu.', requestId);
  }

  const rawCursor = params.get('cursor');
  const cursor = rawCursor === null ? undefined : decodeCatalogCursor(rawCursor);
  if (rawCursor !== null && cursor === null) {
    // Un curseur illisible est une erreur explicite, pas une première page
    // silencieuse : le consommateur croirait paginer et rebouclerait (§15.1).
    return jsonError('VALIDATION_ERROR', 'Curseur illisible.', requestId);
  }

  const rawLimit = params.get('limit');
  const limit = rawLimit === null ? 50 : Number.parseInt(rawLimit, 10);
  if (Number.isNaN(limit) || limit < 1) {
    return jsonError('VALIDATION_ERROR', 'Paramètre limit invalide.', requestId);
  }

  const [{ events, nextCursor }, sourceStatus] = await Promise.all([
    fetchEventsCatalog({
      ...(since === undefined ? {} : { since }),
      ...(until === undefined ? {} : { until }),
      ...(rawDepartment === null ? {} : { department: rawDepartment.toUpperCase() }),
      ...(rawVerification === null ? {} : { verification: rawVerification }),
      ...(cursor == null ? {} : { cursor }),
      limit: Math.min(limit, 100),
    }),
    fetchSourceStatus(),
  ]);

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
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: {
        generatedAt: new Date().toISOString(),
        ...(since === undefined ? {} : { since: since.toISOString() }),
        ...(nextCursor === null ? {} : { nextCursor }),
        sources: toMetaSources(sourceStatus.sources.filter((s) => s.key === 'firms')),
        disclaimer:
          'Événements déduits de détections satellitaires, non équivalents à des confirmations officielles.',
      },
    },
  );
}
