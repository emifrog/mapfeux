import type maplibregl from 'maplibre-gl';

import type { ImageCoordinates } from '@/lib/radar/timeline';

import { DEPARTMENTS_FILL_LAYER_ID } from './department-layer';
import { EVENTS_TAIL_LAYER_ID } from './event-layer';

/**
 * Couche image du radar de précipitations. Cahier §19.3 et FR-123.
 *
 * Une frame est une **image géoréférencée** en Web Mercator : la source
 * MapLibre `image` la cale sur ses quatre coins, exacts puisque l'image a
 * été reprojetée dans cette grille par le worker. L'animation change
 * l'image de la source, jamais la couche — et le fondu raster est coupé :
 * un fondu de 300 ms entre deux frames fabriquerait des fantômes de pluie.
 */

export const RADAR_SOURCE_ID = 'mapfeux-radar';
export const RADAR_LAYER_ID = 'mapfeux-radar-image';

export interface RadarFrameDisplay {
  url: string;
  coordinates: ImageCoordinates;
}

/** La première couche au-dessus du fond : le radar se glisse sous le reste. */
function firstOverlayLayerId(map: maplibregl.Map): string | undefined {
  for (const layerId of [DEPARTMENTS_FILL_LAYER_ID, EVENTS_TAIL_LAYER_ID]) {
    if (map.getLayer(layerId) !== undefined) return layerId;
  }
  return undefined;
}

export function removeRadarLayer(map: maplibregl.Map): void {
  if (map.getLayer(RADAR_LAYER_ID) !== undefined) map.removeLayer(RADAR_LAYER_ID);
  if (map.getSource(RADAR_SOURCE_ID) !== undefined) map.removeSource(RADAR_SOURCE_ID);
}

/** Pose la couche ou change sa frame — sous les lavis et les événements. */
export function setRadarFrame(map: maplibregl.Map, frame: RadarFrameDisplay): void {
  const existing = map.getSource(RADAR_SOURCE_ID) as maplibregl.ImageSource | undefined;
  if (existing !== undefined) {
    existing.updateImage({ url: frame.url, coordinates: frame.coordinates });
    return;
  }

  map.addSource(RADAR_SOURCE_ID, {
    type: 'image',
    url: frame.url,
    coordinates: frame.coordinates,
  });
  map.addLayer(
    {
      id: RADAR_LAYER_ID,
      type: 'raster',
      source: RADAR_SOURCE_ID,
      paint: {
        'raster-opacity': 0.7,
        'raster-fade-duration': 0,
        'raster-resampling': 'nearest',
      },
    },
    firstOverlayLayerId(map),
  );
}
