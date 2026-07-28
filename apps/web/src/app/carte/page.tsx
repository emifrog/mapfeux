import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';

import { EventList } from '@/components/event-list';
import { MapLegend } from '@/components/map/legend';
import { MapView } from '@/components/map/map-view';
import { fetchFiresInBbox } from '@/lib/data/events';

/**
 * Carte nationale. Cahier §7.1, FR-001 à FR-007.
 *
 * Le premier lot d'événements est chargé par le serveur : la liste textuelle
 * fonctionne sans JavaScript, et la carte affiche quelque chose sans attendre
 * un aller-retour. Les lots suivants suivent l'emprise (FR-007).
 */

export const metadata: Metadata = {
  title: 'Carte',
  description:
    'Carte des détections thermiques satellitaires regroupées en événements, en France métropolitaine et en Corse.',
};

export const revalidate = 120;

// Emprise de départ : les territoires pilotes. Servir la France entière
// dépasserait le plafond de surface de l'API, et n'aurait rien à montrer
// ailleurs tant que l'ingestion n'est pas nationale.
const INITIAL_BBOX = { minLon: 5.2, minLat: 42.6, maxLon: 8.0, maxLat: 44.6 };

export default async function MapPage() {
  const events = await fetchFiresInBbox(INITIAL_BBOX, { limit: 500 });
  const now = new Date();

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Carte des événements</h1>
      <p className="mt-2 max-w-3xl text-sm text-stone-800">{MAP_DISCLAIMER}</p>

      <div className="h-104 mt-5 overflow-hidden rounded border border-stone-300">
        <MapView
          center={[
            (INITIAL_BBOX.minLon + INITIAL_BBOX.maxLon) / 2,
            (INITIAL_BBOX.minLat + INITIAL_BBOX.maxLat) / 2,
          ]}
          zoom={8}
          className="h-full w-full"
          events={events.map((event) => ({
            publicId: event.publicId,
            freshnessStatus: event.freshnessStatus,
            detectionCount: event.detectionCount,
            location: event.location,
            nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
          }))}
          reloadOnMove
        />
      </div>

      <div className="mt-4">
        <MapLegend />
      </div>

      <section aria-labelledby="liste" className="mt-8">
        <h2 id="liste" className="text-xl font-semibold">
          Événements de la zone
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          {events.length} événement{events.length > 1 ? 's' : ''} au chargement de la page. Cette
          liste ne suit pas les déplacements de la carte : elle décrit l’emprise initiale, et son
          horodatage vaut pour elle seule.
        </p>

        <div className="mt-4">
          <EventList events={events} now={now} />
        </div>
      </section>

      <p className="mt-8 text-xs text-stone-500">
        Page générée le{' '}
        <time dateTime={now.toISOString()}>
          {new Intl.DateTimeFormat('fr-FR', {
            dateStyle: 'long',
            timeStyle: 'short',
            timeZone: 'Europe/Paris',
          }).format(now)}
        </time>
        . Emprise initiale : territoires pilotes 06 et 83.
      </p>
    </div>
  );
}
