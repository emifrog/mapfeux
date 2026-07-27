import { jsonSuccess, newRequestId } from '@/lib/api/response';
import { fetchSourceStatus, toMetaSources } from '@/lib/sources';

/**
 * GET /api/v1/status — santé synthétique. Cahier §15.2, FR-110.
 *
 * L'endpoint reste disponible même lorsque toutes les sources sont en échec :
 * c'est précisément la situation où il est le plus consulté.
 *
 * Trois états, jamais deux. « unknown » n'est pas « operational » : ne pas
 * savoir n'est pas aller bien, et annoncer le contraire serait exactement la
 * fausse assurance que le cahier §5.13 interdit.
 */
export async function GET(): Promise<Response> {
  const requestId = newRequestId();
  const result = await fetchSourceStatus();
  const generatedAt = new Date().toISOString();

  const degraded = result.sources.filter((s) => s.freshness !== 'fresh').map((s) => s.key);

  const status = !result.readable
    ? 'unknown'
    : degraded.length === 0 && result.sources.length > 0
      ? 'operational'
      : 'degraded';

  return jsonSuccess(
    {
      status,
      degradedSources: degraded,
      sourceCount: result.sources.length,
      requestId,
    },
    {
      sMaxAge: 30,
      staleWhileRevalidate: 120,
      meta: {
        generatedAt,
        sources: toMetaSources(result.sources),
      },
    },
  );
}
