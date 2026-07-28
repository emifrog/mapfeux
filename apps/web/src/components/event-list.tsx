import { dataAgeMs, formatDataAge } from '@mapfeux/domain';
import { CONFIDENCE_LEVEL_LABELS, EVENT_FRESHNESS_LABELS } from '@mapfeux/ui';
import Link from 'next/link';

import type { FireSummary } from '@/lib/data/events';

/**
 * Liste textuelle des événements de l'emprise.
 *
 * Référence : cahier §8.6, §6.5 et §17.7.
 *
 * Ce n'est pas un pis-aller pour lecteurs d'écran : c'est un chemin d'accès à
 * part entière, rendu par le serveur, qui fonctionne sans JavaScript, sans
 * WebGL et sur une connexion dégradée.
 *
 * La liste est scindée en deux, comme la carte : les événements étayés
 * d'abord, puis la longue traîne des observations isolées. Rien n'est masqué —
 * le cahier l'interdit — mais rien n'est mis sur le même plan non plus, car
 * une centaine de points équivalents ne s'interprète pas.
 */

function EventEntry({
  event,
  now,
  formatter,
  muted,
}: {
  event: FireSummary;
  now: Date;
  formatter: Intl.DateTimeFormat;
  muted: boolean;
}) {
  return (
    <li className="py-3">
      <Link
        href={`/evenements/${event.publicId}`}
        className={`underline underline-offset-4 ${muted ? '' : 'font-medium'}`}
      >
        {event.nearestMunicipality?.name ?? 'Événement thermique'}
      </Link>
      <span className="mono ml-2 text-xs" style={{ color: 'var(--text-3)' }}>
        {event.publicId}
      </span>

      <p className="mt-1 text-sm" style={{ color: 'var(--text-2)' }}>
        {EVENT_FRESHNESS_LABELS[event.freshnessStatus]} · {event.detectionCount} détection
        {event.detectionCount > 1 ? 's' : ''} · fiabilité{' '}
        {CONFIDENCE_LEVEL_LABELS[event.confidenceLevel].toLowerCase()}
      </p>

      <p className="text-sm" style={{ color: 'var(--text-3)' }}>
        Dernière observation{' '}
        <time dateTime={event.lastDetectedAt.toISOString()}>
          {formatter.format(event.lastDetectedAt)}
        </time>{' '}
        (il y a {formatDataAge(dataAgeMs(event.lastDetectedAt, now))})
      </p>
    </li>
  );
}

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
      <p style={{ color: 'var(--text-2)' }}>
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

  const substantiated = events.filter((event) => event.confidenceLevel !== 'low');
  const tail = events.filter((event) => event.confidenceLevel === 'low');

  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="etayes">
        <h3 id="etayes" className="text-base font-semibold">
          Événements étayés
          <span className="mono ml-2 text-sm font-normal" style={{ color: 'var(--text-3)' }}>
            {substantiated.length}
          </span>
        </h3>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-2)' }}>
          Observés à plusieurs reprises, ou par plusieurs capteurs indépendants.
        </p>

        {substantiated.length === 0 ? (
          <p className="mt-3 text-sm" style={{ color: 'var(--text-2)' }}>
            Aucun événement étayé dans cette zone.
          </p>
        ) : (
          <ul className="mt-2 divide-y" style={{ borderColor: 'var(--border)' }}>
            {substantiated.map((event) => (
              <EventEntry
                key={event.publicId}
                event={event}
                now={now}
                formatter={formatter}
                muted={false}
              />
            ))}
          </ul>
        )}
      </section>

      {tail.length > 0 && (
        <section aria-labelledby="traine">
          <h3 id="traine" className="text-base font-semibold">
            Observations isolées
            <span className="mono ml-2 text-sm font-normal" style={{ color: 'var(--text-3)' }}>
              {tail.length}
            </span>
          </h3>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-2)' }}>
            Vues une seule fois, ou sans confirmation par un second capteur. La plupart
            correspondent à des brûlages agricoles, des sites industriels ou des artefacts. Elles
            sont conservées et consultables, mais ne sont pas mises en avant.
          </p>

          <ul className="mt-2 divide-y" style={{ borderColor: 'var(--border)' }}>
            {tail.map((event) => (
              <EventEntry
                key={event.publicId}
                event={event}
                now={now}
                formatter={formatter}
                muted
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
