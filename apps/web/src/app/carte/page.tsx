import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';

import { EventList } from '@/components/event-list';
import { MapLegend } from '@/components/map/legend';
import { MapView } from '@/components/map/map-view';
import { fetchEventsInBbox } from '@/lib/data/events';

/**
 * Carte nationale. Cahier §7.1, FR-001 à FR-007.
 *
 * Le premier lot d'événements est chargé par le serveur : la liste textuelle
 * fonctionne sans JavaScript, et la carte affiche quelque chose sans attendre
 * un aller-retour. Les lots suivants suivent l'emprise (FR-007).
 *
 * ## Mise en page
 *
 * La carte occupe toute la largeur de la coque ; la liste et les textes
 * restent dans une colonne de lecture. Une carte étirée sur 1240 px se lit
 * mieux qu'une carte contrainte, alors qu'une ligne de texte de 1240 px ne se
 * lit pas du tout.
 *
 * La légende est posée **à côté** de la carte sur grand écran, en dessous
 * sinon. Sous la carte à toutes les tailles, elle tombait hors de vue au
 * moment précis où l'on regarde les points sans savoir ce qu'ils veulent dire.
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
  const events = await fetchEventsInBbox(INITIAL_BBOX, { limit: 500 });
  const now = new Date();

  const generatedAt = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Europe/Paris',
  }).format(now);

  return (
    <div className="shell py-10">
      <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-2">
        <span>carte</span>
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>territoires pilotes 06 et 83</span>
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>observation satellitaire</span>
      </nav>

      <h1 className="text-display mt-3 max-w-[16ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Anomalies thermiques observées
      </h1>

      <p className="text-lead text-(--text-2) mt-4 max-w-[68ch]">{MAP_DISCLAIMER}</p>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1fr_320px] lg:items-start">
        <div
          className="sm:h-104 lg:h-136 h-96 overflow-hidden rounded-lg border"
          style={{ borderColor: 'var(--border-strong)' }}
        >
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
              lastDetectedAt: event.lastDetectedAt.toISOString(),
              confidence: event.confidenceLevel,
              detectionCount: event.detectionCount,
              location: event.location,
              nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
            }))}
            reloadOnMove
          />
        </div>

        <MapLegend />
      </div>

      <section aria-labelledby="liste" className="mt-12 max-w-[840px]">
        <h2 id="liste" className="text-title font-bold tracking-tight">
          Événements de la zone
        </h2>
        <p className="text-small text-(--text-2) mt-2 max-w-[68ch]">
          <span className="mono">{events.length}</span> événement
          {events.length > 1 ? 's' : ''} au chargement de la page. Cette liste ne suit pas les
          déplacements de la carte : elle décrit l’emprise initiale, et son horodatage vaut pour
          elle seule.
        </p>

        <div className="mt-6">
          <EventList events={events} now={now} />
        </div>
      </section>

      <p className="text-micro text-(--text-3) mt-12 max-w-[68ch]">
        Page générée le{' '}
        <time dateTime={now.toISOString()} className="mono">
          {generatedAt}
        </time>
        . Emprise initiale : territoires pilotes 06 et 83.
      </p>
    </div>
  );
}
