import { DETECTION_COUNT_RADIUS_EXPRESSION, FRESHNESS_COLOR_EXPRESSION } from '@mapfeux/map-style';
import type { FeatureCollection } from 'geojson';
import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';

/**
 * Couche des événements thermiques.
 *
 * Référence : cahier §8.2 et FR-003.
 *
 * Séparée du composant React : l'ajout d'une source et de couches MapLibre est
 * de l'impératif sur un objet mutable, mal servi par le cycle de rendu de
 * React. Isolé ici, il reste lisible et remplaçable.
 */

export const EVENTS_SOURCE_ID = 'mapfeux-events';
export const EVENTS_CIRCLE_LAYER_ID = 'mapfeux-events-circle';
export const EVENTS_HALO_LAYER_ID = 'mapfeux-events-halo';

export interface MapEvent {
  publicId: string;
  freshnessStatus: string;
  detectionCount: number;
  location: { longitude: number; latitude: number };
  nearestMunicipalityName: string | null;
}

export function toFeatureCollection(events: MapEvent[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: events.map((event) => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [event.location.longitude, event.location.latitude],
      },
      properties: {
        publicId: event.publicId,
        freshness: event.freshnessStatus,
        detectionCount: event.detectionCount,
        municipality: event.nearestMunicipalityName ?? '',
      },
    })),
  };
}

export function addEventLayer(map: MapLibreMap, events: MapEvent[]): void {
  if (map.getSource(EVENTS_SOURCE_ID) !== undefined) return;

  map.addSource(EVENTS_SOURCE_ID, {
    type: 'geojson',
    data: toFeatureCollection(events),
  });

  // Halo blanc sous le marqueur : sans lui, un point sombre sur un fond IGN
  // sombre devient invisible, et la carte ment par omission.
  map.addLayer({
    id: EVENTS_HALO_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    paint: {
      'circle-radius': [
        '+',
        DETECTION_COUNT_RADIUS_EXPRESSION,
        2,
      ] as unknown as ExpressionSpecification,
      'circle-color': '#ffffff',
      'circle-opacity': 0.85,
    },
  });

  map.addLayer({
    id: EVENTS_CIRCLE_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    paint: {
      'circle-radius': DETECTION_COUNT_RADIUS_EXPRESSION as unknown as ExpressionSpecification,
      'circle-color': FRESHNESS_COLOR_EXPRESSION as unknown as ExpressionSpecification,
      'circle-opacity': 0.85,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#44403c',
    },
  });
}

export function updateEventLayer(map: MapLibreMap, events: MapEvent[]): void {
  const source = map.getSource(EVENTS_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(toFeatureCollection(events));
}
