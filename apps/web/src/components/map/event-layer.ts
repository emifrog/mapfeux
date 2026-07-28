import {
  DETECTION_COUNT_RADIUS_EXPRESSION,
  FRESHNESS_COLOR_EXPRESSION,
  LONG_TAIL_FILTER,
  LONG_TAIL_RADIUS,
  PALETTE,
  SUBSTANTIATED_FILTER,
} from '@mapfeux/map-style';
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
export const EVENTS_TAIL_LAYER_ID = 'mapfeux-events-tail';

export interface MapEvent {
  publicId: string;
  freshnessStatus: string;
  /** Heure de la dernière observation, source de la couleur du marqueur. */
  lastDetectedAt: string;
  /** Détermine si l'événement est rendu en aplat ou en anneau discret. */
  confidence: string;
  detectionCount: number;
  location: { longitude: number; latitude: number };
  nearestMunicipalityName: string | null;
}

/**
 * L'âge est calculé à la construction de la couche, pas figé côté serveur.
 *
 * Une page peut rester ouverte des heures pendant une crise : une couleur
 * calculée au rendu vieillirait sans changer, et afficherait « moins de 3 h »
 * sur une observation devenue vieille de six.
 */
export function toFeatureCollection(events: MapEvent[], now = new Date()): FeatureCollection {
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
        confidence: event.confidence,
        ageHours: Math.max(
          0,
          (now.getTime() - new Date(event.lastDetectedAt).getTime()) / 3_600_000,
        ),
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
  // La traîne d'abord, donc dessous : un anneau creux, de rayon fixe. Sa
  // taille ne doit rien suggérer d'un phénomène dont on ne sait presque rien.
  map.addLayer({
    id: EVENTS_TAIL_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: LONG_TAIL_FILTER as unknown as ExpressionSpecification,
    paint: {
      'circle-radius': LONG_TAIL_RADIUS,
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-width': 1.4,
      'circle-stroke-color': FRESHNESS_COLOR_EXPRESSION as unknown as ExpressionSpecification,
      'circle-stroke-opacity': 0.7,
    },
  });

  map.addLayer({
    id: EVENTS_HALO_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: SUBSTANTIATED_FILTER as unknown as ExpressionSpecification,
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
    filter: SUBSTANTIATED_FILTER as unknown as ExpressionSpecification,
    paint: {
      'circle-radius': DETECTION_COUNT_RADIUS_EXPRESSION as unknown as ExpressionSpecification,
      'circle-color': FRESHNESS_COLOR_EXPRESSION as unknown as ExpressionSpecification,
      'circle-opacity': 0.85,
      'circle-stroke-width': 1,
      'circle-stroke-color': PALETTE.boundary,
    },
  });
}

/** Couches cliquables : la traîne reste accessible au même titre. */
export const CLICKABLE_LAYER_IDS = [EVENTS_CIRCLE_LAYER_ID, EVENTS_TAIL_LAYER_ID];

export function updateEventLayer(map: MapLibreMap, events: MapEvent[]): void {
  const source = map.getSource(EVENTS_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(toFeatureCollection(events));
}
