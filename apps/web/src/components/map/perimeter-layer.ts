import { PALETTE } from '@mapfeux/map-style';
import type maplibregl from 'maplibre-gl';

/**
 * Couche des périmètres d'événement — cahier FR-092 et FR-093.
 *
 * FR-093 est porté par la structure même : `line-dasharray` n'étant pas
 * pilotable par donnée, l'officiel et l'institutionnel ont **leur** couche au
 * trait plein et à la couleur d'autorité ; tout le reste — EFFIS, estimé,
 * historique, éditorial — passe par la couche au trait tireté, dans la
 * famille du calcul. Un périmètre satellitaire ne peut pas ressembler à un
 * contour opérationnel : il n'existe pas de chemin de code qui le dessinerait
 * ainsi. La couleur ne porte jamais seule le sens (§6.5) : la fiche nomme
 * chaque version à côté de la carte.
 */

export interface PerimeterShape {
  id: string;
  perimeterType: string;
  geometry: GeoJSON.MultiPolygon;
}

const SOURCE_ID = 'perimeters';
export const PERIMETERS_FILL_LAYER_ID = 'perimeters-fill';
export const PERIMETERS_LINE_OFFICIAL_LAYER_ID = 'perimeters-line-official';
export const PERIMETERS_LINE_INDICATIVE_LAYER_ID = 'perimeters-line-indicative';

const OPERATIONAL_TYPES = ['official', 'institutional'];

const COLOR_BY_TYPE: maplibregl.ExpressionSpecification = [
  'match',
  ['get', 'perimeterType'],
  'official',
  PALETTE.official,
  'institutional',
  PALETTE.official,
  'editorial',
  PALETTE.neutral.strong,
  PALETTE.inference,
];

function featureCollection(perimeters: PerimeterShape[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: perimeters.map((perimeter) => ({
      type: 'Feature',
      geometry: perimeter.geometry,
      properties: { id: perimeter.id, perimeterType: perimeter.perimeterType },
    })),
  };
}

export function addPerimeterLayer(map: maplibregl.Map, perimeters: PerimeterShape[]): void {
  if (map.getSource(SOURCE_ID) !== undefined) return;

  map.addSource(SOURCE_ID, { type: 'geojson', data: featureCollection(perimeters) });

  // Le lavis reste discret : le périmètre encadre les détections, il ne les
  // recouvre pas — l'orange thermique demeure la seule couleur qui compte.
  map.addLayer({
    id: PERIMETERS_FILL_LAYER_ID,
    type: 'fill',
    source: SOURCE_ID,
    paint: { 'fill-color': COLOR_BY_TYPE, 'fill-opacity': 0.08 },
  });

  map.addLayer({
    id: PERIMETERS_LINE_OFFICIAL_LAYER_ID,
    type: 'line',
    source: SOURCE_ID,
    filter: ['in', ['get', 'perimeterType'], ['literal', OPERATIONAL_TYPES]],
    paint: { 'line-color': COLOR_BY_TYPE, 'line-width': 2 },
  });

  map.addLayer({
    id: PERIMETERS_LINE_INDICATIVE_LAYER_ID,
    type: 'line',
    source: SOURCE_ID,
    filter: ['!', ['in', ['get', 'perimeterType'], ['literal', OPERATIONAL_TYPES]]],
    paint: {
      'line-color': COLOR_BY_TYPE,
      'line-width': 2,
      'line-dasharray': [2, 2],
    },
  });
}

export function updatePerimeterLayer(map: maplibregl.Map, perimeters: PerimeterShape[]): void {
  const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  if (source === undefined) {
    addPerimeterLayer(map, perimeters);
    return;
  }
  source.setData(featureCollection(perimeters));
}
