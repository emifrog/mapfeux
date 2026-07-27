/**
 * Stratégie de zoom et de charge de données.
 * Référence : cahier §21.3 et FR-007.
 *
 * Le principe est de ne jamais charger une géométrie que l'utilisateur ne peut
 * pas distinguer : les limites communales n'apparaissent qu'à partir du niveau
 * où elles sont lisibles, et les détections brutes uniquement en vue locale.
 */

export interface ZoomTier {
  readonly minZoom: number;
  readonly maxZoom: number;
  readonly departmentAggregates: boolean;
  readonly groupedEvents: boolean;
  readonly municipalities: boolean;
  readonly smokePlumes: boolean;
  readonly rawDetections: boolean;
}

export const ZOOM_TIERS: readonly ZoomTier[] = [
  {
    minZoom: 0,
    maxZoom: 6,
    departmentAggregates: true,
    groupedEvents: false,
    municipalities: false,
    smokePlumes: false,
    rawDetections: false,
  },
  {
    minZoom: 7,
    maxZoom: 9,
    departmentAggregates: true,
    groupedEvents: true,
    municipalities: false,
    smokePlumes: false,
    rawDetections: false,
  },
  {
    minZoom: 10,
    maxZoom: 12,
    departmentAggregates: false,
    groupedEvents: true,
    municipalities: true,
    smokePlumes: true,
    rawDetections: false,
  },
  {
    minZoom: 13,
    maxZoom: 22,
    departmentAggregates: false,
    groupedEvents: true,
    municipalities: true,
    smokePlumes: true,
    rawDetections: true,
  },
];

export function tierForZoom(zoom: number): ZoomTier {
  const clamped = Math.max(0, Math.min(22, zoom));
  const tier = ZOOM_TIERS.find((t) => clamped >= t.minZoom && clamped <= t.maxZoom);
  // Le dernier palier couvre jusqu'au zoom maximal : ce repli est défensif.
  return tier ?? ZOOM_TIERS[ZOOM_TIERS.length - 1]!;
}

/** Vue par défaut : France métropolitaine et Corse. FR-001 */
export const DEFAULT_VIEW = {
  center: [2.55, 46.6] as const,
  zoom: 5.2,
  maxBounds: [
    [-6.5, 40.5],
    [11.5, 51.7],
  ] as const,
};
