import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';

import { MapView } from '@/components/map/map-view';

/**
 * Carte nationale plein écran. Cahier §7.1 et FR-001.
 *
 * Les couches de détections et d'événements arrivent avec le lot 3. La carte
 * affiche pour l'instant le seul fond territorial : mieux vaut un fond nu qu'un
 * calque vide laissant croire à l'absence de détections.
 */

export const metadata: Metadata = {
  title: 'Carte',
  description:
    'Carte des détections thermiques satellitaires en France métropolitaine et en Corse.',
};

export default function MapPage() {
  return (
    <div className="flex h-[calc(100vh-12rem)] min-h-[24rem] flex-col">
      <p className="border-b border-stone-200 bg-stone-50 px-4 py-2 text-xs text-stone-800">
        {MAP_DISCLAIMER}
      </p>
      <MapView className="flex-1" />
    </div>
  );
}
