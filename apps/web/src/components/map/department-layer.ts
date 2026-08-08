import {
  DEPARTMENT_EVENTS_FILL_EXPRESSION,
  DEPARTMENT_OUTLINE_COLOR,
  DEPARTMENT_OUTLINE_OPACITY,
} from '@mapfeux/map-style';
import type { ExpressionSpecification, Map as MapLibreMap } from 'maplibre-gl';

/**
 * Couche des agrégats départementaux. Cahier FR-003, §21.2 et §21.3.
 *
 * Aux faibles zooms, la carte ne charge ni géométries communales ni
 * événements individuels : les polygones départementaux viennent des tuiles
 * PMTiles publiées par `build-admin-tiles.py`, et les comptes arrivent par
 * `/api/v1/events/departments`, posés en `feature-state` — la géométrie et la
 * donnée voyagent séparément, chacune à son rythme de cache.
 *
 * Au-delà du zoom 9, les événements individuels prennent le relais (§21.3) ;
 * le contour départemental reste, discret, jusqu'au zoom 12.
 */

export const DEPARTMENTS_SOURCE_ID = 'mapfeux-territoires';
export const DEPARTMENTS_FILL_LAYER_ID = 'mapfeux-departements-remplissage';
export const DEPARTMENTS_OUTLINE_LAYER_ID = 'mapfeux-departements-contour';

const SOURCE_LAYER = 'departements';

/** Le remplissage s'efface là où les événements individuels arrivent. */
const FILL_MAX_ZOOM = 9;
const OUTLINE_MAX_ZOOM = 12;

export interface DepartmentAggregate {
  departmentCode: string;
  departmentSlug: string;
  departmentStatus: string;
  events: number;
  substantiated: number;
  lastDetectedAt: string;
}

export function addDepartmentLayer(map: MapLibreMap, tilesUrl: string): void {
  if (map.getSource(DEPARTMENTS_SOURCE_ID) !== undefined) return;

  map.addSource(DEPARTMENTS_SOURCE_ID, {
    type: 'vector',
    url: `pmtiles://${tilesUrl}`,
    // Le `feature-state` s'adresse à une entité par identifiant : le code
    // départemental est l'identifiant naturel, promu depuis les attributs.
    promoteId: { [SOURCE_LAYER]: 'code' },
  });

  map.addLayer({
    id: DEPARTMENTS_FILL_LAYER_ID,
    type: 'fill',
    source: DEPARTMENTS_SOURCE_ID,
    'source-layer': SOURCE_LAYER,
    maxzoom: FILL_MAX_ZOOM,
    paint: {
      'fill-color': DEPARTMENT_EVENTS_FILL_EXPRESSION as unknown as ExpressionSpecification,
    },
  });

  map.addLayer({
    id: DEPARTMENTS_OUTLINE_LAYER_ID,
    type: 'line',
    source: DEPARTMENTS_SOURCE_ID,
    'source-layer': SOURCE_LAYER,
    maxzoom: OUTLINE_MAX_ZOOM,
    paint: {
      'line-color': DEPARTMENT_OUTLINE_COLOR,
      'line-opacity': DEPARTMENT_OUTLINE_OPACITY,
      'line-width': 1,
    },
  });
}

/**
 * Pose les comptes en `feature-state`. Les états précédents sont effacés
 * d'abord : un département retombé à zéro doit s'éteindre, pas garder sa
 * couleur d'il y a cinq minutes.
 */
export function setDepartmentAggregates(map: MapLibreMap, aggregates: DepartmentAggregate[]): void {
  if (map.getSource(DEPARTMENTS_SOURCE_ID) === undefined) return;

  map.removeFeatureState({ source: DEPARTMENTS_SOURCE_ID, sourceLayer: SOURCE_LAYER });
  for (const aggregate of aggregates) {
    map.setFeatureState(
      {
        source: DEPARTMENTS_SOURCE_ID,
        sourceLayer: SOURCE_LAYER,
        id: aggregate.departmentCode,
      },
      { events: aggregate.events, substantiated: aggregate.substantiated },
    );
  }
}
