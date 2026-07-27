'use client';

import { buildIgnBasemapStyle, DEFAULT_VIEW } from '@mapfeux/map-style';
import maplibregl, { type StyleSpecification } from 'maplibre-gl';
import { useEffect, useRef } from 'react';

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
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export default function BaseMap({
  center = DEFAULT_VIEW.center,
  zoom = DEFAULT_VIEW.zoom,
  bounded = true,
  className,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

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
      style: buildIgnBasemapStyle() as StyleSpecification,
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

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Volontairement sans dépendances : la carte se crée une fois.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
