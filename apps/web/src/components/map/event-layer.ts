import {
  DETECTION_COUNT_RADIUS_EXPRESSION,
  FRESHNESS_COLOR_EXPRESSION,
  LONG_TAIL_FILTER,
  LONG_TAIL_RADIUS,
  CLUSTER_MAX_ZOOM,
  CLUSTER_RADIUS_EXPRESSION,
  CLUSTER_RADIUS_PX,
  freshnessColorExpression,
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
/** Lueur sous les événements récents : la couleur d'âge, diffuse. */
export const EVENTS_GLOW_LAYER_ID = 'mapfeux-events-glow';
/** Grappes sous le zoom 9 : disque compté, couleur du membre le plus récent. */
export const CLUSTERS_GLOW_LAYER_ID = 'mapfeux-clusters-glow';
export const CLUSTERS_CIRCLE_LAYER_ID = 'mapfeux-clusters-circle';
export const CLUSTERS_COUNT_LAYER_ID = 'mapfeux-clusters-count';

/** Un marqueur et non une grappe : ce que voient les couches de points. */
const NOT_CLUSTERED = ['!', ['has', 'point_count']] as const;
/** Une grappe dont le membre le plus récent a moins de vingt-quatre heures. */
const CLUSTER_RECENT_FILTER = [
  'all',
  ['has', 'point_count'],
  ['<', ['get', 'minAge'], 24],
] as const;

/**
 * Moins de vingt-quatre heures : les trois premiers paliers de la légende,
 * ceux qui portent une couleur chaude. Un événement archivé n'a pas de
 * lueur — il n'a rien à annoncer.
 */
const RECENT_FILTER = ['<', ['get', 'ageHours'], 24] as const;

/**
 * Ce qu'une observation seule sait d'elle-même — la ligne du tableau de la
 * fiche. Portée par un marqueur de l'empreinte, elle change ce que la
 * carte au survol raconte : une acquisition, pas un événement.
 */
export interface MapObservation {
  sensor: string;
  satellite: string;
  dayNight: string | null;
  frpMw: number | null;
  /** Confiance de l'observation, `'unknown'` compris. */
  confidence: string;
}

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
  /**
   * Présent quand le marqueur est **une observation** de l'empreinte d'un
   * événement — la fiche, la relecture — et non l'événement lui-même.
   */
  observation?: MapObservation;
}

/**
 * Les propriétés d'une observation, à plat : MapLibre sérialise un objet
 * imbriqué en chaîne, et une valeur `null` n'a pas à voyager pour être
 * relue comme absente.
 */
function observationProperties(observation: MapObservation): Record<string, string | number> {
  return {
    kind: 'observation',
    sensor: observation.sensor,
    satellite: observation.satellite,
    observationConfidence: observation.confidence,
    ...(observation.dayNight === null ? {} : { dayNight: observation.dayNight }),
    ...(observation.frpMw === null ? {} : { frpMw: observation.frpMw }),
  };
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
        // Pour la carte au survol, qui compte l'âge depuis **maintenant** :
        // `ageHours` ci-dessus est figé à la construction de la couche et
        // ne sert qu'à la couleur.
        lastDetectedAt: event.lastDetectedAt,
        ...(event.observation === undefined ? {} : observationProperties(event.observation)),
      },
    })),
  };
}

export function addEventLayer(map: MapLibreMap, events: MapEvent[], now = new Date()): void {
  if (map.getSource(EVENTS_SOURCE_ID) !== undefined) return;

  map.addSource(EVENTS_SOURCE_ID, {
    type: 'geojson',
    data: toFeatureCollection(events, now),
    // Regroupement sous le zoom 9 (§21.3) : au zoom 7, trois événements de
    // Fos tiennent dans dix pixels et se recouvrent. Une grappe porte son
    // compte, l'âge de son membre le plus récent — c'est lui qui la colore —
    // et le nombre d'étayés, pour que la carte au survol garde le
    // vocabulaire de la liste.
    cluster: true,
    clusterMaxZoom: CLUSTER_MAX_ZOOM,
    clusterRadius: CLUSTER_RADIUS_PX,
    clusterProperties: {
      minAge: ['min', ['get', 'ageHours']],
      substantiated: [
        '+',
        ['case', SUBSTANTIATED_FILTER as unknown as ExpressionSpecification, 1, 0],
      ],
    },
  });

  // --- Les grappes ------------------------------------------------------------
  map.addLayer({
    id: CLUSTERS_GLOW_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: CLUSTER_RECENT_FILTER as unknown as ExpressionSpecification,
    paint: {
      'circle-radius': ['*', CLUSTER_RADIUS_EXPRESSION, 1.8] as unknown as ExpressionSpecification,
      'circle-color': freshnessColorExpression('minAge') as unknown as ExpressionSpecification,
      'circle-opacity': 0.35,
      'circle-blur': 1,
    },
  });

  map.addLayer({
    id: CLUSTERS_CIRCLE_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: ['has', 'point_count'],
    paint: {
      'circle-radius': CLUSTER_RADIUS_EXPRESSION as unknown as ExpressionSpecification,
      'circle-color': freshnessColorExpression('minAge') as unknown as ExpressionSpecification,
      'circle-opacity': 0.92,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': PALETTE.boundary,
    },
  });

  // Le compte, en gras, avec un halo sombre : lisible sur l'orange comme
  // sur le gris. La police est une de celles que la Géoplateforme sert
  // avec son style — les glyphes viennent de là.
  map.addLayer({
    id: CLUSTERS_COUNT_LAYER_ID,
    type: 'symbol',
    source: EVENTS_SOURCE_ID,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': ['get', 'point_count_abbreviated'],
      'text-font': ['Source Sans Pro Bold'],
      'text-size': 11,
      'text-allow-overlap': true,
    },
    paint: {
      'text-color': '#ffffff',
      'text-halo-color': 'rgba(0, 0, 0, 0.45)',
      'text-halo-width': 1,
    },
  });

  // Halo blanc sous le marqueur : sans lui, un point sombre sur un fond IGN
  // sombre devient invisible, et la carte ment par omission.
  // La traîne d'abord, donc dessous : un anneau creux, de rayon fixe. Sa
  // taille ne doit rien suggérer d'un phénomène dont on ne sait presque rien.
  map.addLayer({
    id: EVENTS_TAIL_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: ['all', NOT_CLUSTERED, LONG_TAIL_FILTER] as unknown as ExpressionSpecification,
    paint: {
      'circle-radius': LONG_TAIL_RADIUS,
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-width': 1.4,
      'circle-stroke-color': FRESHNESS_COLOR_EXPRESSION as unknown as ExpressionSpecification,
      'circle-stroke-opacity': 0.7,
    },
  });

  // La lueur, sous le halo : un disque flou dans la couleur d'âge, deux
  // fois le rayon. C'est ce qui fait qu'un événement de la nuit se voit
  // de loin sur le fond sombre, et que l'orange reste le seul propos
  // chaud de la carte (§8.1) — il n'est posé que là où quelque chose
  // vient d'être observé.
  map.addLayer({
    id: EVENTS_GLOW_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: [
      'all',
      NOT_CLUSTERED,
      SUBSTANTIATED_FILTER,
      RECENT_FILTER,
    ] as unknown as ExpressionSpecification,
    paint: {
      'circle-radius': [
        '*',
        DETECTION_COUNT_RADIUS_EXPRESSION,
        2.2,
      ] as unknown as ExpressionSpecification,
      'circle-color': FRESHNESS_COLOR_EXPRESSION as unknown as ExpressionSpecification,
      'circle-opacity': 0.35,
      'circle-blur': 1,
    },
  });

  map.addLayer({
    id: EVENTS_HALO_LAYER_ID,
    type: 'circle',
    source: EVENTS_SOURCE_ID,
    filter: ['all', NOT_CLUSTERED, SUBSTANTIATED_FILTER] as unknown as ExpressionSpecification,
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
    filter: ['all', NOT_CLUSTERED, SUBSTANTIATED_FILTER] as unknown as ExpressionSpecification,
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

/** Toutes les couches d'événements, dans l'ordre de dessin — pour les remonter d'un bloc. */
export const EVENT_LAYER_IDS = [
  CLUSTERS_GLOW_LAYER_ID,
  CLUSTERS_CIRCLE_LAYER_ID,
  CLUSTERS_COUNT_LAYER_ID,
  EVENTS_TAIL_LAYER_ID,
  EVENTS_GLOW_LAYER_ID,
  EVENTS_HALO_LAYER_ID,
  EVENTS_CIRCLE_LAYER_ID,
];

export function updateEventLayer(map: MapLibreMap, events: MapEvent[], now = new Date()): void {
  const source = map.getSource(EVENTS_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(toFeatureCollection(events, now));
}
