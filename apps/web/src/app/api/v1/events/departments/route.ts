import type { NextRequest } from 'next/server';

import { jsonError, jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchDepartmentAggregates } from '@/lib/data/events';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/events/departments — agrégats par département. FR-003, §21.2.
 *
 * La réponse nationale tient en quelques dizaines de lignes là où l'endpoint
 * par emprise refuse une bbox France entière : c'est le pendant serveur de la
 * stratégie de zoom (§21.3). Les départements sans événement sont absents —
 * l'absence n'est pas une donnée à transporter.
 */

const DEFAULT_WINDOW_DAYS = 7;

export async function GET(request: NextRequest): Promise<Response> {
  const requestId = newRequestId();

  const rawSince = request.nextUrl.searchParams.get('since');
  let since: Date;
  if (rawSince === null) {
    since = new Date(Date.now() - DEFAULT_WINDOW_DAYS * 24 * 3_600_000);
  } else {
    since = new Date(rawSince);
    if (Number.isNaN(since.getTime())) {
      return jsonError(
        'VALIDATION_ERROR',
        'Paramètre since invalide, attendu ISO 8601.',
        requestId,
      );
    }
  }

  const [aggregates, sourceStatus] = await Promise.all([
    fetchDepartmentAggregates(since),
    fetchSourceStatus(),
  ]);

  return jsonSuccess(
    aggregates.map((row) => ({
      departmentCode: row.departmentCode,
      departmentSlug: row.departmentSlug,
      departmentStatus: row.departmentStatus,
      events: row.events,
      substantiated: row.substantiated,
      lastDetectedAt: row.lastDetectedAt.toISOString(),
    })),
    {
      sMaxAge: 60,
      staleWhileRevalidate: 300,
      meta: {
        generatedAt: new Date().toISOString(),
        since: since.toISOString(),
        sources: toMetaSources(sourceStatus.sources.filter((s) => s.key === 'firms')),
        disclaimer:
          'Comptes d’événements déduits de détections satellitaires, agrégés par département.',
      },
    },
  );
}
