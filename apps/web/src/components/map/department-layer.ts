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
/** Les noms, du zoom 6 au zoom 8,5 : le squelette a besoin d'être nommé. */
export const DEPARTMENTS_LABEL_LAYER_ID = 'mapfeux-departements-noms';

const SOURCE_LAYER = 'departements';

/** Le remplissage s'efface là où les événements individuels arrivent. */
const FILL_MAX_ZOOM = 9;
const OUTLINE_MAX_ZOOM = 12;

/**
 * Le lavis s'efface en fondu à mesure que les événements prennent le relais.
 *
 * La stratégie de zoom (§21.3) donne l'agrégat départemental comme sujet aux
 * zooms 4-6, puis les événements aux zooms 7 et au-delà. Sans ce fondu, un
 * lavis monté à 50 % d'opacité restait peint jusqu'au zoom 9 **par-dessus**
 * les marqueurs auxquels il devait céder : au zoom 8, cadrage par défaut de
 * `/carte`, les disques disparaissaient dans le saumon. Un agrégat qui
 * masque le détail qu'il annonce ne renseigne plus, il cache.
 */
const FILL_OPACITY_BY_ZOOM = ['interpolate', ['linear'], ['zoom'], 6, 1, 7, 0.3, 8, 0] as const;

export interface DepartmentAggregate {
  departmentCode: string;
  departmentSlug: string;
  departmentStatus: string;
  /** Nom et destination, pour la liste nationale — nuls si le registre ne les a pas. */
  departmentName: string | null;
  center: { longitude: number; latitude: number } | null;
  defaultZoom: number | null;
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
      'fill-opacity': FILL_OPACITY_BY_ZOOM as unknown as ExpressionSpecification,
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

  // Les noms, entre le lavis national et la carte de quartier. Au zoom 7,
  // regardé le 13 septembre 2026, la carte n'était qu'un trait de côte et
  // des contours sans nom : on ne savait pas où l'on était. Petites
  // capitales grises, jamais en concurrence avec un marqueur — pas de
  // superposition autorisée, le nom s'efface devant le point. Le fond IGN
  // garde ses propres toponymes ; ceux-ci s'arrêtent où les siens
  // commencent à suffire.
  map.addLayer({
    id: DEPARTMENTS_LABEL_LAYER_ID,
    type: 'symbol',
    source: DEPARTMENTS_SOURCE_ID,
    'source-layer': SOURCE_LAYER,
    minzoom: 6,
    maxzoom: 8.5,
    layout: {
      'text-field': ['upcase', ['get', 'nom']],
      'text-font': ['Source Sans Pro Regular'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 6, 9, 8, 12],
      'text-letter-spacing': 0.12,
      'text-allow-overlap': false,
      'text-padding': 8,
    },
    paint: {
      'text-color': DEPARTMENT_OUTLINE_COLOR,
      'text-opacity': 0.75,
      'text-halo-color': 'rgba(0, 0, 0, 0.35)',
      'text-halo-width': 1,
    },
  });
}

/**
 * L'étendue d'un département, lue dans les tuiles déjà chargées — ou `null`
 * si elles ne le portent pas encore.
 *
 * Mener la carte au **centre** d'un département ne suffit pas : le
 * 15 septembre 2026, « Pyrénées-Atlantiques · 80 événements » menait au
 * zoom 9 sur son centre, où l'on n'en voyait aucun — ils étaient tous à
 * Hendaye, au bord. L'étendue, elle, garantit que le département entier
 * tient dans la zone visible. Les tuiles découpent un polygone par carreau,
 * avec une marge : l'union des boîtes déborde d'un peu, jamais en dedans.
 */
export function departmentBounds(
  map: MapLibreMap,
  code: string,
): [[number, number], [number, number]] | null {
  const features = map.querySourceFeatures(DEPARTMENTS_SOURCE_ID, {
    sourceLayer: SOURCE_LAYER,
    filter: ['==', ['get', 'code'], code],
  });

  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  const visit = (coordinates: unknown): void => {
    if (!Array.isArray(coordinates)) return;
    if (typeof coordinates[0] === 'number' && typeof coordinates[1] === 'number') {
      minLon = Math.min(minLon, coordinates[0]);
      maxLon = Math.max(maxLon, coordinates[0]);
      minLat = Math.min(minLat, coordinates[1]);
      maxLat = Math.max(maxLat, coordinates[1]);
      return;
    }
    for (const child of coordinates) visit(child);
  };
  for (const feature of features) {
    if (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon') {
      visit(feature.geometry.coordinates);
    }
  }

  if (!Number.isFinite(minLon) || !Number.isFinite(minLat)) return null;
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
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
