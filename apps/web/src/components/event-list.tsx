import { dataAgeMs, formatDataAge } from '@mapfeux/domain';
import { FRESHNESS_COLORS } from '@mapfeux/map-style';
import { CONFIDENCE_LEVEL_LABELS, EVENT_FRESHNESS_LABELS } from '@mapfeux/ui';
import Link from 'next/link';

import type { EventSummary } from '@/lib/data/events';

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
 *
 * ## Pourquoi la liste emprunte les formes de la carte
 *
 * Disque plein pour un événement étayé, anneau creux pour une observation
 * isolée : ce sont exactement les symboles de la carte et de sa légende. Deux
 * vocabulaires pour une même distinction obligeraient à apprendre deux fois la
 * même chose, et laisseraient croire que la liste dit autre chose.
 *
 * La couleur du repère suit l'**âge de l'observation**, comme sur la carte, et
 * jamais la gravité — que MapFeux ne connaît pas. Elle ne porte aucune
 * information seule : chaque entrée écrit son statut et son horodatage.
 */

function AgeMarker({ freshnessStatus, hollow }: { freshnessStatus: string; hollow: boolean }) {
  const color = FRESHNESS_COLORS[freshnessStatus] ?? FRESHNESS_COLORS.archived;
  return (
    <span
      aria-hidden="true"
      className="mt-1.75 block size-2.5 shrink-0 rounded-full"
      style={
        hollow
          ? { border: `1.5px solid ${color}` }
          : { backgroundColor: color, border: `1.5px solid ${color}` }
      }
    />
  );
}

function EventEntry({
  event,
  now,
  formatter,
  muted,
}: {
  event: EventSummary;
  now: Date;
  formatter: Intl.DateTimeFormat;
  muted: boolean;
}) {
  return (
    <li className="flex gap-3 py-3.5">
      <AgeMarker freshnessStatus={event.freshnessStatus} hollow={muted} />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <Link
            href={`/evenements/${event.publicId}`}
            className={`underline-offset-4 hover:underline ${muted ? '' : 'font-semibold'}`}
          >
            {event.nearestMunicipality?.name ?? 'Événement thermique'}
          </Link>
          <span className="eyebrow">{event.publicId}</span>
        </div>

        {/* Le décompte en chasse fixe : c'est une mesure, pas un énoncé. */}
        <p className="text-small text-(--text-2) mt-1">
          {EVENT_FRESHNESS_LABELS[event.freshnessStatus]}
          <span aria-hidden="true" className="text-(--border-strong) mx-2">
            ·
          </span>
          <span className="mono">{event.detectionCount}</span> détection
          {event.detectionCount > 1 ? 's' : ''}
          <span aria-hidden="true" className="text-(--border-strong) mx-2">
            ·
          </span>
          fiabilité {CONFIDENCE_LEVEL_LABELS[event.confidenceLevel].toLowerCase()}
        </p>

        <p className="text-small text-(--text-3) mt-0.5">
          Dernière observation{' '}
          <time dateTime={event.lastDetectedAt.toISOString()} className="mono">
            {formatter.format(event.lastDetectedAt)}
          </time>{' '}
          (il y a {formatDataAge(dataAgeMs(event.lastDetectedAt, now))})
        </p>
      </div>
    </li>
  );
}

function Section({
  id,
  title,
  count,
  lead,
  children,
}: {
  id: string;
  title: string;
  count: number;
  lead: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <h3 id={id} className="flex items-baseline gap-2.5 font-bold tracking-tight">
        {title}
        {/* Le compte est une mesure : chasse fixe, et jamais dans le titre
            lui-même — il change à chaque emprise, pas le libellé. */}
        <span className="mono text-small text-(--text-3) font-normal">{count}</span>
      </h3>
      <p className="text-small text-(--text-2) mt-1 max-w-[68ch]">{lead}</p>
      {children}
    </section>
  );
}

export function EventList({
  events,
  now,
  timeZone = 'Europe/Paris',
}: {
  events: EventSummary[];
  now: Date;
  timeZone?: string;
}) {
  if (events.length === 0) {
    return (
      <p className="text-(--text-2) max-w-[68ch]">
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
    <div className="flex flex-col gap-9">
      <Section
        id="etayes"
        title="Événements étayés"
        count={substantiated.length}
        lead="Observés à plusieurs reprises, ou par plusieurs capteurs indépendants."
      >
        {substantiated.length === 0 ? (
          <p className="text-small text-(--text-2) mt-3">Aucun événement étayé dans cette zone.</p>
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
      </Section>

      {tail.length > 0 && (
        <Section
          id="traine"
          title="Observations isolées"
          count={tail.length}
          lead="Vues une seule fois, ou sans confirmation par un second capteur. La plupart correspondent à des brûlages agricoles, des sites industriels ou des artefacts. Elles sont conservées et consultables, mais ne sont pas mises en avant."
        >
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
        </Section>
      )}
    </div>
  );
}
