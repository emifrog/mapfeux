import { dataAgeMs, formatDataAge } from '@mapfeux/domain';
import { CONFIDENCE_LEVEL_LABELS, EVENT_FRESHNESS_LABELS } from '@mapfeux/ui';
import Link from 'next/link';

import type { FireSummary } from '@/lib/data/events';

/**
 * Liste textuelle des événements de l'emprise.
 *
 * Référence : cahier §8.6 et §6.5.
 *
 * Ce n'est pas un pis-aller pour lecteurs d'écran : c'est un chemin d'accès à
 * part entière, rendu par le serveur, qui fonctionne sans JavaScript, sans
 * WebGL et sur une connexion dégradée. La carte l'illustre, elle ne le
 * remplace pas.
 */

export function EventList({
  events,
  now,
  timeZone = 'Europe/Paris',
}: {
  events: FireSummary[];
  now: Date;
  timeZone?: string;
}) {
  if (events.length === 0) {
    return (
      <p className="text-stone-700">
        Aucun événement dans cette zone pour la période consultée. Cela signifie qu’aucune détection
        thermique n’a été regroupée ici, pas qu’il ne s’y passe rien.
      </p>
    );
  }

  const formatter = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone,
  });

  return (
    <ul className="divide-y divide-stone-200">
      {events.map((event) => (
        <li key={event.publicId} className="py-3">
          <Link
            href={`/evenements/${event.publicId}`}
            className="font-medium underline underline-offset-4"
          >
            {event.nearestMunicipality?.name ?? 'Événement thermique'}
          </Link>
          <span className="ml-2 font-mono text-xs text-stone-600">{event.publicId}</span>

          <p className="mt-1 text-sm text-stone-700">
            {EVENT_FRESHNESS_LABELS[event.freshnessStatus]} · {event.detectionCount} détection
            {event.detectionCount > 1 ? 's' : ''} · fiabilité{' '}
            {CONFIDENCE_LEVEL_LABELS[event.confidenceLevel].toLowerCase()}
          </p>

          <p className="text-sm text-stone-600">
            Dernière observation{' '}
            <time dateTime={event.lastDetectedAt.toISOString()}>
              {formatter.format(event.lastDetectedAt)}
            </time>{' '}
            (il y a {formatDataAge(dataAgeMs(event.lastDetectedAt, now))})
          </p>
        </li>
      ))}
    </ul>
  );
}
