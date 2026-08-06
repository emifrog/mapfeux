'use client';

import { DEFAULT_VIEW, ignVectorStyleUrl } from '@mapfeux/map-style';
import maplibregl from 'maplibre-gl';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

import { addEventLayer, CLICKABLE_LAYER_IDS, updateEventLayer, type MapEvent } from './event-layer';

import 'maplibre-gl/dist/maplibre-gl.css';

/**
 * Carte MapLibre.
 *
 * Référence : cahier §8.3 et §6.5.
 *
 * Accessibilité : MapLibre gère la navigation clavier sur son canevas, mais une
 * carte reste inaccessible aux lecteurs d'écran. Elle n'est jamais le seul
 * moyen d'accéder à l'information — la liste textuelle synchronisée du §8.6 est
 * livrée avec les événements, et la recherche de commune reste utilisable sans
 * jamais toucher la carte.
 */

export interface BaseMapProps {
  center?: readonly [number, number];
  zoom?: number;
  /** Restreint le déplacement. Par défaut, la France métropolitaine et la Corse. */
  bounded?: boolean;
  className?: string;
  /** Événements à afficher. Le premier lot vient du rendu serveur. */
  events?: MapEvent[];
  /** Recharge les événements lorsque l'emprise change. FR-007. */
  reloadOnMove?: boolean;
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Recharge les événements de l'emprise visible. FR-007.
 *
 * Un échec est silencieux côté carte : les marqueurs déjà affichés restent, ce
 * qui vaut mieux que de les effacer. La liste textuelle rendue par le serveur
 * porte, elle, l'horodatage de son propre chargement.
 */
async function reload(map: maplibregl.Map): Promise<void> {
  const bounds = map.getBounds();
  const bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
    .map((value) => value.toFixed(4))
    .join(',');

  try {
    const response = await fetch(`/api/v1/events?bbox=${bbox}&limit=500`);
    if (!response.ok) return;

    const payload = (await response.json()) as {
      data: {
        id: string;
        freshnessStatus: string;
        lastDetectedAt: string;
        confidence: string;
        detectionCount: number;
        location: { coordinates: [number, number] };
        nearestMunicipality: { name: string } | null;
      }[];
    };

    updateEventLayer(
      map,
      payload.data.map((event) => ({
        publicId: event.id,
        freshnessStatus: event.freshnessStatus,
        lastDetectedAt: event.lastDetectedAt,
        confidence: event.confidence,
        detectionCount: event.detectionCount,
        location: {
          longitude: event.location.coordinates[0],
          latitude: event.location.coordinates[1],
        },
        nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
      })),
    );
  } catch {
    // Emprise trop large ou réseau coupé : on garde l'affichage précédent.
  }
}

export default function BaseMap({
  center = DEFAULT_VIEW.center,
  zoom = DEFAULT_VIEW.zoom,
  bounded = true,
  className,
  events = [],
  reloadOnMove = false,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const router = useRouter();

  // Le premier lot vient du serveur : la liste textuelle est rendue sans
  // JavaScript, et la carte n'attend pas un aller-retour pour montrer quelque
  // chose. Les lots suivants sont chargés à l'emprise.
  //
  // La ref n'est initialisée qu'ici et mise à jour dans un effet : la muter
  // pendant le rendu rendrait le composant non réentrant.
  const eventsRef = useRef<MapEvent[]>(events);

  // Initialisation unique. Les changements de cadrage passent par l'effet
  // suivant : recréer la carte à chaque navigation rechargerait toutes les
  // tuiles pour rien.
  useEffect(() => {
    const container = containerRef.current;
    if (container === null || mapRef.current !== null) return;

    // `exactOptionalPropertyTypes` interdit de passer `maxBounds: undefined` :
    // la propriété est ajoutée seulement lorsqu'elle a une valeur.
    const boundsOption = bounded
      ? {
          maxBounds: [
            [DEFAULT_VIEW.maxBounds[0][0], DEFAULT_VIEW.maxBounds[0][1]],
            [DEFAULT_VIEW.maxBounds[1][0], DEFAULT_VIEW.maxBounds[1][1]],
          ] satisfies [[number, number], [number, number]],
        }
      : {};

    const map = new maplibregl.Map({
      container,
      // Style vectoriel « gris » de la Géoplateforme : le fond se retire pour
      // que l'orange des détections soit la seule couleur qui compte (§8.1).
      // MapLibre charge l'URL lui-même ; `buildIgnBasemapStyle` reste le repli
      // raster, et sert l'orthophotographie.
      style: ignVectorStyleUrl('gris'),
      center: [center[0], center[1]],
      zoom,
      ...boundsOption,
      // L'attribution IGN est obligatoire et ne doit pas être repliée. §9.5
      attributionControl: { compact: false },
      // Le relief incliné n'apporte rien à la lecture d'une détection et
      // complique la comparaison des distances.
      pitchWithRotate: false,
      dragRotate: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');

    map.on('load', () => {
      addEventLayer(map, eventsRef.current);

      // Un clic ouvre la fiche : la carte oriente vers l'événement, elle ne
      // prétend pas le décrire. Toute l'information sourcée est sur la fiche.
      //
      // La traîne est cliquable au même titre que le reste : elle est rendue
      // discrète, pas inaccessible.
      for (const layerId of CLICKABLE_LAYER_IDS) {
        map.on('click', layerId, (event) => {
          const publicId = event.features?.[0]?.properties?.['publicId'];
          if (typeof publicId === 'string') {
            router.push(`/evenements/${publicId}`);
          }
        });

        map.on('mouseenter', layerId, () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
        });
      }

      if (reloadOnMove) {
        map.on('moveend', () => void reload(map));
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Volontairement sans dépendances : la carte se crée une fois.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mise à jour de la couche lorsque le serveur fournit un nouveau lot.
  useEffect(() => {
    eventsRef.current = events;
    const map = mapRef.current;
    if (map !== null && map.isStyleLoaded()) {
      updateEventLayer(map, events);
    }
  }, [events]);

  // Recadrage lorsque le territoire consulté change.
  useEffect(() => {
    const map = mapRef.current;
    if (map === null) return;

    if (prefersReducedMotion()) {
      map.jumpTo({ center: [center[0], center[1]], zoom });
    } else {
      map.flyTo({ center: [center[0], center[1]], zoom, duration: 800 });
    }
  }, [center, zoom]);

  return (
    <div
      ref={containerRef}
      className={className}
      // Le canevas est focusable par MapLibre ; ce libellé annonce ce qu'il est.
      role="application"
      aria-label="Carte des détections thermiques"
    />
  );
}
