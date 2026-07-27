'use client';

import dynamic from 'next/dynamic';

import type { BaseMapProps } from './base-map';

/**
 * Enveloppe de chargement de la carte.
 *
 * MapLibre touche `window` dès son import et pèse lourd : il est chargé
 * uniquement côté navigateur et seulement sur les pages qui affichent une
 * carte. Le cahier §6.2 impose de maîtriser la taille du JavaScript initial ;
 * embarquer le moteur cartographique sur la page méthodologie serait une faute.
 */
const BaseMap = dynamic(() => import('./base-map'), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-full w-full items-center justify-center bg-stone-100 text-sm text-stone-600"
      role="status"
    >
      Chargement de la carte…
    </div>
  ),
});

export function MapView(props: BaseMapProps) {
  return <BaseMap {...props} />;
}
