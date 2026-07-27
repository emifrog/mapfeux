/**
 * Contrats territoires et communes.
 * Référence : cahier §15.2, §5.2 et §5.3.
 */

import { TERRITORY_STATUS, TERRITORY_TYPE } from '@mapfeux/domain';
import { z } from 'zod';

import { inseeCodeSchema, latitudeSchema, longitudeSchema, pointSchema } from './common';

export const territoryTypeSchema = z.enum(TERRITORY_TYPE);
export const territoryStatusSchema = z.enum(TERRITORY_STATUS);

export const territorySchema = z.object({
  slug: z.string().min(1).max(64),
  code: z.string().min(1).max(16),
  type: territoryTypeSchema,
  name: z.string(),
  shortName: z.string().nullable(),
  parentSlug: z.string().nullable(),
  status: territoryStatusSchema,
  timezone: z.string(),
  center: pointSchema,
  defaultZoom: z.number().min(0).max(22),
});

export type Territory = z.infer<typeof territorySchema>;

export const municipalitySearchQuerySchema = z.object({
  q: z.string().min(1).max(80),
  limit: z.coerce.number().int().min(1).max(25).default(10),
});

export const municipalitySchema = z.object({
  insee: inseeCodeSchema,
  name: z.string(),
  departmentCode: z.string(),
  departmentName: z.string().nullable(),
  postalCodes: z.array(z.string()),
  centroid: pointSchema,
});

export type Municipality = z.infer<typeof municipalitySchema>;

/**
 * `POST /api/v1/location/resolve` — résolution d'un point vers sa commune.
 * Les coordonnées ne sont ni journalisées ni conservées. §22.2
 */
export const resolveLocationBodySchema = z.object({
  longitude: longitudeSchema,
  latitude: latitudeSchema,
});

export type ResolveLocationBody = z.infer<typeof resolveLocationBodySchema>;
