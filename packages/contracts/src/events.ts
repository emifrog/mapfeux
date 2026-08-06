/**
 * Contrats des endpoints `/api/v1/events`.
 * Référence : cahier §15.2, §15.3, §15.4 et §5.6.
 *
 * L'API dit « événement », jamais « feu » : le vocabulaire public (§2.4)
 * interdit de présenter une détection thermique comme un incendie, et le nom
 * de la ressource est la première formulation que voit un consommateur.
 */

import {
  CONFIDENCE_LEVEL,
  EVENT_FRESHNESS,
  OFFICIAL_CONTROL_STATUS,
  TIMELINE_ENTRY_TYPE,
  VERIFICATION_STATUS,
} from '@mapfeux/domain';
import { z } from 'zod';

import {
  bboxSchema,
  confidenceLevelSchema,
  inseeCodeSchema,
  isoInstantSchema,
  pointSchema,
  provenanceSchema,
} from './common';

export const eventFreshnessSchema = z.enum(EVENT_FRESHNESS);
export const verificationStatusSchema = z.enum(VERIFICATION_STATUS);
export const officialControlStatusSchema = z.enum(OFFICIAL_CONTROL_STATUS);
export const timelineEntryTypeSchema = z.enum(TIMELINE_ENTRY_TYPE);

/** Identifiant public opaque, non séquentiel. §5.5 FR-041 */
export const publicEventIdSchema = z
  .string()
  .regex(/^[A-Z]{2,4}-[0-9A-HJ-NP-Z]{6,10}$/, 'Identifiant public invalide');

/** Paramètres de `GET /api/v1/events`. §15.4 */
export const eventsQuerySchema = z.object({
  bbox: bboxSchema.optional(),
  since: isoInstantSchema.optional(),
  until: isoInstantSchema.optional(),
  status: z.union([eventFreshnessSchema, z.array(eventFreshnessSchema)]).optional(),
  confidence: z.enum(CONFIDENCE_LEVEL).optional(),
  sensor: z.string().max(32).optional(),
  territory: z.string().max(64).optional(),
  include: z.array(z.enum(['smokeSummary'])).optional(),
  limit: z.coerce.number().int().min(1).max(500).default(200),
});

export type EventsQuery = z.infer<typeof eventsQuerySchema>;

/** Résumé d'événement renvoyé sur la carte. */
export const eventSummarySchema = z.object({
  id: publicEventIdSchema,
  freshnessStatus: eventFreshnessSchema,
  verificationStatus: verificationStatusSchema,
  officialControlStatus: officialControlStatusSchema.nullable(),
  firstDetectedAt: isoInstantSchema,
  lastDetectedAt: isoInstantSchema,
  location: pointSchema,
  nearestMunicipality: z.object({ insee: inseeCodeSchema, name: z.string() }).nullable(),
  detectionCount: z.number().int().nonnegative(),
  confidence: confidenceLevelSchema,
});

export type EventSummary = z.infer<typeof eventSummarySchema>;

/** Fiche complète. §5.6 */
export const eventDetailSchema = eventSummarySchema.extend({
  sensors: z.array(z.string()),
  frpMw: z
    .object({
      min: z.number().nullable(),
      median: z.number().nullable(),
      max: z.number().nullable(),
    })
    .nullable(),
  /** Provenance obligatoire, bloc par bloc. §2.4 */
  provenance: z.object({
    event: provenanceSchema,
    detections: provenanceSchema,
    smoke: provenanceSchema.optional(),
    officialStatus: provenanceSchema.optional(),
  }),
  officialStatusSource: z
    .object({
      organisation: z.string(),
      url: z.string().url().nullable(),
      publishedAt: isoInstantSchema,
    })
    .nullable(),
  timeline: z.object({
    latestEntryAt: isoInstantSchema.nullable(),
    entryCount: z.number().int().nonnegative(),
  }),
  smoke: z
    .object({
      available: z.boolean(),
      validFrom: isoInstantSchema.nullable(),
      validTo: isoInstantSchema.nullable(),
      confidence: confidenceLevelSchema.nullable(),
      provenance: provenanceSchema,
      modelRun: z.object({ model: z.string(), runAt: isoInstantSchema }).nullable(),
    })
    .nullable(),
});

export type EventDetail = z.infer<typeof eventDetailSchema>;

/** Entrée de chronologie publique. §13.9 — les notes internes ne sortent jamais. */
export const timelineEntrySchema = z.object({
  id: z.string().uuid(),
  entryType: timelineEntryTypeSchema,
  provenance: provenanceSchema,
  occurredAt: isoInstantSchema,
  recordedAt: isoInstantSchema,
  title: z.string(),
  summary: z.string().nullable(),
  source: z.object({ name: z.string(), url: z.string().url().nullable() }).nullable(),
});

export type TimelineEntry = z.infer<typeof timelineEntrySchema>;

/** Commune potentiellement concernée. §5.9 */
export const affectedMunicipalitySchema = z.object({
  insee: inseeCodeSchema,
  name: z.string(),
  firstIntersectionAt: isoInstantSchema.nullable(),
  lastIntersectionAt: isoInstantSchema.nullable(),
  overlapRatio: z.number().min(0).max(1).nullable(),
  exposureRank: z.number().int().positive(),
  confidence: confidenceLevelSchema,
});

export type AffectedMunicipality = z.infer<typeof affectedMunicipalitySchema>;
