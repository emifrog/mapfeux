/**
 * Primitives partagées par tous les endpoints `/api/v1`.
 * Référence : cahier §15.1.
 */

import { CONFIDENCE_LEVEL, PROVENANCE, SOURCE_FRESHNESS } from '@mapfeux/domain';
import { z } from 'zod';

/** Instant ISO 8601 en UTC. Toute date exposée passe par ce schéma. */
export const isoInstantSchema = z
  .string()
  .datetime({ offset: true })
  .describe('Date ISO 8601 en UTC');

export const provenanceSchema = z.enum(PROVENANCE);
export const confidenceLevelSchema = z.enum(CONFIDENCE_LEVEL);
export const sourceFreshnessSchema = z.enum(SOURCE_FRESHNESS);

/** Code INSEE d'une commune : cinq caractères, la Corse utilisant 2A/2B. */
export const inseeCodeSchema = z.string().regex(/^(?:\d{5}|2[AB]\d{3})$/, 'Code INSEE invalide');

export const longitudeSchema = z.number().min(-180).max(180);
export const latitudeSchema = z.number().min(-90).max(90);

export const pointSchema = z.object({
  type: z.literal('Point'),
  coordinates: z.tuple([longitudeSchema, latitudeSchema]),
});

/** Surface maximale d'une emprise interrogeable, en degrés carrés. §21.4 */
export const MAX_BBOX_AREA_DEG2 = 30;

/**
 * Emprise `minLon,minLat,maxLon,maxLat`.
 * Les bornes sont validées avant toute requête PostGIS. §15.4
 */
export const bboxSchema = z.string().transform((value, ctx) => {
  const parts = value.split(',');
  if (parts.length !== 4) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'INVALID_BBOX' });
    return z.NEVER;
  }
  const numbers = parts.map((part) => Number.parseFloat(part.trim()));
  if (numbers.some((n) => !Number.isFinite(n))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'INVALID_BBOX' });
    return z.NEVER;
  }
  const [minLon, minLat, maxLon, maxLat] = numbers as [number, number, number, number];
  if (minLon >= maxLon || minLat >= maxLat) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'INVALID_BBOX' });
    return z.NEVER;
  }
  if (minLon < -180 || maxLon > 180 || minLat < -90 || maxLat > 90) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'INVALID_BBOX' });
    return z.NEVER;
  }
  if ((maxLon - minLon) * (maxLat - minLat) > MAX_BBOX_AREA_DEG2) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'BBOX_TOO_LARGE' });
    return z.NEVER;
  }
  return { minLon, minLat, maxLon, maxLat };
});

export type BoundingBox = z.infer<typeof bboxSchema>;

/** Fraîcheur d'une source telle qu'exposée dans `meta.sources`. */
export const sourceStateSchema = z.object({
  status: sourceFreshnessSchema,
  dataAt: isoInstantSchema.nullable(),
});

/**
 * Métadonnées présentes sur toute réponse publique.
 * `lastKnownSnapshotAt` permet à l'interface d'annoncer un mode dégradé plutôt
 * que de présenter une donnée de cache comme actuelle. §21.5
 */
export const responseMetaSchema = z.object({
  generatedAt: isoInstantSchema,
  lastKnownSnapshotAt: isoInstantSchema.nullable().optional(),
  /** Début de la fenêtre couverte, pour les réponses agrégées sur une période. */
  since: isoInstantSchema.optional(),
  /** Curseur de la page suivante, opaque. Absent : dernière page. §15.1 */
  nextCursor: z.string().optional(),
  sources: z.record(z.string(), sourceStateSchema),
  disclaimer: z.string().optional(),
});

export type ResponseMeta = z.infer<typeof responseMetaSchema>;

/** Enveloppe `{ data, meta }` commune à toutes les réponses. */
export function envelopeSchema<T extends z.ZodTypeAny>(data: T) {
  return z.object({ data, meta: responseMetaSchema });
}

/** Pagination par curseur : jamais d'offset sur les tables volumineuses. §15.1 */
export const cursorPageSchema = z.object({
  cursor: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(500).default(100),
});
