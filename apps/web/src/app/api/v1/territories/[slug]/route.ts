import { jsonError, jsonSuccess, jsonUnavailable, newRequestId } from '@/lib/api/response';
import { fetchOfficialLinks, fetchTerritory } from '@/lib/data/territories';

/**
 * GET /api/v1/territories/{slug} — détail d'un territoire et ses liens
 * officiels. Cahier §15.2 et FR-100.
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ slug: string }> },
): Promise<Response> {
  const requestId = newRequestId();
  const { slug } = await context.params;

  const read = await fetchTerritory(slug);
  if (!read.readable) return jsonUnavailable(requestId);
  const territory = read.value;
  if (territory === null) {
    return jsonError('NOT_FOUND', 'Ce territoire n’est pas disponible.', requestId);
  }

  const officialLinks = await fetchOfficialLinks(slug);
  // Des liens non lus ne sont pas « aucun lien » : la réponse les porte,
  // elle ne sort pas sans eux.
  if (!officialLinks.readable) return jsonUnavailable(requestId);

  return jsonSuccess(
    { ...territory, officialLinks: officialLinks.value },
    {
      sMaxAge: 3600,
      staleWhileRevalidate: 86_400,
      meta: {
        generatedAt: new Date().toISOString(),
        sources: {},
      },
    },
  );
}
