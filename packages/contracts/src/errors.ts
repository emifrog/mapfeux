/**
 * Codes d'erreur stables de l'API publique.
 * Référence : cahier annexe E. Les codes ne changent pas de sens entre versions.
 */

import { z } from 'zod';

export const API_ERROR_CODE = [
  'INVALID_BBOX',
  'BBOX_TOO_LARGE',
  'NOT_FOUND',
  'SOURCE_DELAYED',
  'SOURCE_UNAVAILABLE',
  'FORECAST_NOT_AVAILABLE',
  'RATE_LIMITED',
  'FORBIDDEN',
  'VALIDATION_ERROR',
  'INTERNAL_ERROR',
] as const;

export type ApiErrorCode = (typeof API_ERROR_CODE)[number];

export const apiErrorCodeSchema = z.enum(API_ERROR_CODE);

/** Statut HTTP associé à chaque code, pour une réponse cohérente. */
export const API_ERROR_HTTP_STATUS: Record<ApiErrorCode, number> = {
  INVALID_BBOX: 400,
  BBOX_TOO_LARGE: 400,
  NOT_FOUND: 404,
  SOURCE_DELAYED: 200,
  SOURCE_UNAVAILABLE: 503,
  FORECAST_NOT_AVAILABLE: 404,
  RATE_LIMITED: 429,
  FORBIDDEN: 403,
  VALIDATION_ERROR: 422,
  INTERNAL_ERROR: 500,
};

export const apiErrorSchema = z.object({
  error: z.object({
    code: apiErrorCodeSchema,
    /** Message destiné au public : jamais de détail technique interne. §5.13 */
    message: z.string(),
    requestId: z.string(),
  }),
});

export type ApiError = z.infer<typeof apiErrorSchema>;
