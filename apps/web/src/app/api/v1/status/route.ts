import { jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/status — santé synthétique. Cahier §15.2, FR-110.
 *
 * L'endpoint reste disponible même lorsque toutes les sources sont en échec :
 * c'est précisément la situation où il est le plus consulté.
 */
export async function GET(): Promise<Response> {
  const requestId = newRequestId();
  const sources = await fetchSourceStatus();
  const generatedAt = new Date().toISOString();

  const degraded = sources.filter((s) => s.freshness !== 'fresh').map((s) => s.key);

  return jsonSuccess(
    {
      status: degraded.length === 0 ? 'operational' : 'degraded',
      degradedSources: degraded,
      sourceCount: sources.length,
      requestId,
    },
    {
      sMaxAge: 30,
      staleWhileRevalidate: 120,
      meta: {
        generatedAt,
        sources: toMetaSources(sources),
      },
    },
  );
}
