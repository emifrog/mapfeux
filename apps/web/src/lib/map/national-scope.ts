import { MAX_BBOX_AREA_DEG2 } from '@mapfeux/contracts';

/**
 * La carte à deux échelles — logique pure, testée seule.
 *
 * Référence : cahier §21.3 (paliers de zoom), §21.4 (surface interrogeable),
 * FR-003, FR-007.
 *
 * ## Deux échelles, pas deux services
 *
 * Jusqu'au 15 septembre 2026, `/carte` s'ouvrait sur l'emprise pilote — le
 * Var et les Alpes-Maritimes — et annonçait quatorze événements, quand
 * l'accueil en annonçait 646 « France entière ». Un visiteur voyait deux
 * services. La carte s'ouvre maintenant sur la France, et ce qu'elle lit
 * dépend de l'échelle :
 *
 * - **national**, sous le zoom 7 : le lavis départemental porte les comptes
 *   (§21.3, palier 0-6) et la colonne de lecture liste les **départements
 *   concernés**. Aucun événement n'est chargé — servir la France entière
 *   en un appel irait contre « ne charger que l'emprise visible » (§21.4),
 *   et la surface interrogeable de l'API le refuse ;
 * - **zone**, à partir du zoom 7 : l'emprise tient sous le plafond, les
 *   événements se chargent, la liste les suit (§8.6).
 *
 * Le seuil n'est pas un réglage d'apparence : au zoom 7 sur une toile de
 * 1 024 px, l'emprise fait environ 17 degrés carrés, sous le plafond de 30 ;
 * au zoom 6, 70. C'est là que la carte peut redevenir une liste
 * d'événements sans mentir sur ce qu'elle a chargé.
 */

export type MapScope = 'national' | 'zone';

/** Premier zoom où l'emprise visible tient sous le plafond de l'API. */
export const ZONE_MIN_ZOOM = 7;

export function scopeForZoom(zoom: number): MapScope {
  return zoom >= ZONE_MIN_ZOOM ? 'zone' : 'national';
}

/** Surface d'une emprise `[minLon, minLat, maxLon, maxLat]`, en degrés carrés. */
export function bboxAreaDeg2(bounds: readonly [number, number, number, number]): number {
  const [minLon, minLat, maxLon, maxLat] = bounds;
  return Math.max(0, maxLon - minLon) * Math.max(0, maxLat - minLat);
}

/**
 * L'emprise peut-elle être demandée à l'API ? Vérifié **avant** l'appel : une
 * emprise trop large recevait un 400 à chaque déplacement national, un
 * aller-retour pour apprendre ce que la géométrie disait déjà.
 */
export function isWithinBboxCap(bounds: readonly [number, number, number, number]): boolean {
  return bboxAreaDeg2(bounds) <= MAX_BBOX_AREA_DEG2;
}

/**
 * Ce que l'API des agrégats rend par département — nom et destination
 * compris, parce que le registre public des territoires ne publie que les
 * départements ouverts (FR-014) et que la France en compte quatre-vingt-seize.
 */
export interface DepartmentAggregateInput {
  departmentCode: string;
  departmentSlug: string;
  departmentStatus: string;
  departmentName: string | null;
  center: { longitude: number; latitude: number } | null;
  defaultZoom: number | null;
  events: number;
  substantiated: number;
  /** ISO 8601. */
  lastDetectedAt: string;
}

export interface DepartmentRow {
  code: string;
  slug: string;
  name: string;
  /** `pilot` ou `active` : une page de territoire existe (FR-015). */
  hasPage: boolean;
  events: number;
  substantiated: number;
  lastDetectedAt: Date;
  /** Où mener la carte quand on choisit ce département. */
  center: [number, number] | null;
  zoom: number | null;
}

/**
 * Les départements concernés, du plus au moins touché. Un département sans
 * nom connu reste dans la liste sous son code, et sans destination : un
 * compte ne disparaît pas faute de nom, et on ne mène pas la carte au hasard.
 */
export function toDepartmentRows(aggregates: readonly DepartmentAggregateInput[]): DepartmentRow[] {
  return aggregates
    .map((aggregate): DepartmentRow => ({
      code: aggregate.departmentCode,
      slug: aggregate.departmentSlug,
      name: aggregate.departmentName?.trim() || aggregate.departmentCode,
      hasPage: aggregate.departmentStatus === 'pilot' || aggregate.departmentStatus === 'active',
      events: aggregate.events,
      substantiated: aggregate.substantiated,
      lastDetectedAt: new Date(aggregate.lastDetectedAt),
      center:
        aggregate.center === null ||
        !Number.isFinite(aggregate.center.longitude) ||
        !Number.isFinite(aggregate.center.latitude)
          ? null
          : [aggregate.center.longitude, aggregate.center.latitude],
      zoom:
        aggregate.defaultZoom === null || !Number.isFinite(aggregate.defaultZoom)
          ? null
          : aggregate.defaultZoom,
    }))
    .sort((a, b) => b.events - a.events || a.name.localeCompare(b.name, 'fr'));
}

export interface NationalSummary {
  events: number;
  substantiated: number;
  departments: number;
}

/** Les totaux que la barre temporelle et la colonne annoncent à l'échelle nationale. */
export function nationalSummary(rows: readonly DepartmentRow[]): NationalSummary {
  return {
    events: rows.reduce((sum, row) => sum + row.events, 0),
    substantiated: rows.reduce((sum, row) => sum + row.substantiated, 0),
    departments: rows.filter((row) => row.events > 0).length,
  };
}
