import 'server-only';

import { API_ERROR_HTTP_STATUS, type ApiErrorCode, type ResponseMeta } from '@mapfeux/contracts';

/**
 * Enveloppe et erreurs de l'API publique.
 *
 * Référence : cahier §15.1 et annexe E.
 *
 * Toute réponse porte `meta.generatedAt` et l'état des sources mobilisées : une
 * page ne doit jamais pouvoir afficher une donnée sans être capable d'en
 * annoncer l'âge (§21.5).
 */

export interface ApiSuccessOptions {
  /** Durée de cache partagé, en secondes. §21.2 */
  sMaxAge?: number;
  /** Fenêtre de service en arrière-plan pendant le rafraîchissement. */
  staleWhileRevalidate?: number;
  meta: ResponseMeta;
}

export function jsonSuccess<T>(data: T, options: ApiSuccessOptions): Response {
  const sMaxAge = options.sMaxAge ?? 60;
  const swr = options.staleWhileRevalidate ?? 300;

  return Response.json(
    { data, meta: options.meta },
    {
      status: 200,
      headers: {
        'Cache-Control': `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`,
        'Content-Type': 'application/json; charset=utf-8',
      },
    },
  );
}

/**
 * Erreur publique. Le message reste compréhensible et ne divulgue aucun détail
 * technique interne : ceux-ci restent dans les journaux serveur (FR-112).
 */
export function jsonError(
  code: ApiErrorCode,
  message: string,
  requestId: string,
  status?: number,
  headers: Record<string, string> = {},
): Response {
  return Response.json(
    { error: { code, message, requestId } },
    {
      status: status ?? API_ERROR_HTTP_STATUS[code],
      headers: {
        'Cache-Control': 'no-store',
        'Content-Type': 'application/json; charset=utf-8',
        ...headers,
      },
    },
  );
}

/**
 * La base n'a pas répondu : 503, jamais mis en cache.
 *
 * Jusqu'au 15 septembre 2026, une lecture manquée sortait en 200 avec une
 * liste vide — gardée une minute par le CDN et lue comme « aucun
 * événement » — ou en 404 sur une fiche qui existe. Le code est celui de
 * l'annexe E pour une source qui ne répond pas : pour l'API, la base en est
 * une. `Retry-After` dit au consommateur quand revenir.
 */
export function jsonUnavailable(
  requestId: string,
  message = 'Les données ne sont pas consultables pour le moment. Réessayez dans quelques instants.',
): Response {
  return jsonError('SOURCE_UNAVAILABLE', message, requestId, undefined, { 'Retry-After': '60' });
}

/** Identifiant de corrélation présent dans la réponse et dans les journaux. */
export function newRequestId(): string {
  return crypto.randomUUID();
}
