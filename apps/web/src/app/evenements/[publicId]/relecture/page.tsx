import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, permanentRedirect } from 'next/navigation';

import { MapView } from '@/components/map/map-view';
import {
  fetchEvent,
  fetchEventDetections,
  fetchEventTimeline,
  resolveEventAlias,
} from '@/lib/data/events';

/**
 * Relecture temporelle d'un événement. Cahier FR-080 à FR-087 et §15.5.
 *
 * L'état à l'instant demandé est **reconstruit à la demande** depuis les
 * observations membres et la chronologie (FR-086) — aucune table de frames.
 * Chaque instant est une URL : `?at=` s'ouvre à l'identique sur un autre
 * appareil (FR-085), et la navigation est une liste de liens — le parcours
 * fonctionne au clavier et sans JavaScript, l'alternative textuelle n'est pas
 * un à-côté, c'est la structure même de la page (FR-083).
 *
 * La page ne rejoue pas les statuts de vérification : elle montre des faits
 * datés — observations, passages, chronologie — sans recopier en TypeScript
 * des règles qui vivent en base. Ce qu'elle affiche est ce qui est **connu et
 * importé**, pas nécessairement la situation réelle de l'époque (FR-087).
 */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ publicId: string }>;
}): Promise<Metadata> {
  const { publicId } = await params;
  return {
    title: `Relecture — ${publicId.toUpperCase()}`,
    robots: { index: false, follow: true },
  };
}

const REPLAY_DISCLAIMER =
  'Cette relecture reconstruit les données connues et importées à chaque ' +
  'instant. Elle ne représente pas nécessairement la situation réelle exacte ' +
  'de l’époque : une observation peut avoir été importée plus tard, ou ' +
  'manquer.';

function formatInstant(value: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(value);
}

export default async function ReplayPage({
  params,
  searchParams,
}: {
  params: Promise<{ publicId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { publicId: rawPublicId } = await params;
  const publicId = rawPublicId.toUpperCase();
  const query = await searchParams;

  const event = await fetchEvent(publicId);
  if (event === null) {
    const canonical = await resolveEventAlias(publicId);
    if (canonical !== null && canonical !== publicId) {
      permanentRedirect(`/evenements/${canonical}/relecture`);
    }
    notFound();
  }

  // Plafond de l'API : 2 000 observations. Atteint, il est annoncé — une
  // relecture tronquée en silence raconterait un feu plus petit que le vrai.
  const DETECTION_CEILING = 2000;
  const [detections, timeline] = await Promise.all([
    fetchEventDetections(publicId, DETECTION_CEILING),
    fetchEventTimeline(publicId),
  ]);
  const truncated = detections.length === DETECTION_CEILING;

  // Les instants de la relecture sont les passages satellitaires : chaque
  // heure d'acquisition distincte est un état consultable (FR-080).
  const instants = [...new Set(detections.map((d) => d.acquiredAt.getTime()))]
    .sort((a, b) => a - b)
    .map((t) => new Date(t));

  const rawAt = typeof query['at'] === 'string' ? query['at'] : undefined;
  const parsedAt = rawAt === undefined ? undefined : new Date(rawAt);
  const at =
    parsedAt === undefined || Number.isNaN(parsedAt.getTime()) ? event.lastDetectedAt : parsedAt;

  const visible = detections.filter((d) => d.acquiredAt.getTime() <= at.getTime());
  const effectiveAt =
    visible.length > 0 ? new Date(Math.max(...visible.map((d) => d.acquiredAt.getTime()))) : null;

  const sensors = [...new Set(visible.map((d) => d.sensor))].sort();
  const frpMax = visible.reduce<number | null>(
    (max, d) => (d.frpMw === null ? max : Math.max(max ?? 0, d.frpMw)),
    null,
  );

  const visibleTimeline = timeline.filter((entry) => entry.occurredAt.getTime() <= at.getTime());

  const currentIndex = instants.findIndex(
    (instant) => effectiveAt !== null && instant.getTime() === effectiveAt.getTime(),
  );
  const previous = currentIndex > 0 ? (instants[currentIndex - 1] ?? null) : null;
  const next =
    currentIndex >= 0 && currentIndex < instants.length - 1
      ? (instants[currentIndex + 1] ?? null)
      : null;

  const tz = event.timeZone;
  const replayHref = (instant: Date) =>
    `/evenements/${event.publicId}/relecture?at=${encodeURIComponent(instant.toISOString())}`;

  return (
    <div className="shell max-w-[75ch] py-14">
      <nav className="text-small text-(--text-2) mono flex flex-wrap items-baseline gap-x-2">
        <Link href={`/evenements/${event.publicId}`} className="hover:text-(--text-2) underline">
          {event.publicId}
        </Link>
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>relecture</span>
      </nav>

      <h1 className="text-display mt-3 max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Relecture
      </h1>
      <p className="text-lead text-(--text-2) mt-4 max-w-[58ch]">
        {event.nearestMunicipality !== null && <>Près de {event.nearestMunicipality.name}. </>}
        Du {formatInstant(event.firstDetectedAt, tz)} au {formatInstant(event.lastDetectedAt, tz)}.
      </p>

      <div
        className="text-small mt-6 rounded-md border-l-[3px] px-5 py-4"
        style={{ background: 'var(--color-age-2-wash)', borderColor: 'var(--color-age-2)' }}
      >
        {REPLAY_DISCLAIMER}
        {truncated && (
          <>
            {' '}
            <strong>
              Relecture partielle : seules les 2 000 observations les plus récentes sont
              reconstituées.
            </strong>
          </>
        )}
      </div>

      <section className="mt-8" aria-labelledby="etat">
        <h2 id="etat" className="text-title font-bold tracking-tight">
          État au {formatInstant(at, tz)}
        </h2>
        {effectiveAt === null ? (
          <p className="text-(--text-2) mt-3">
            Aucune observation n’était encore importée à cet instant.
          </p>
        ) : (
          <dl className="text-small mt-3 grid max-w-[58ch] grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
            <div>
              <dt className="text-(--text-3)">Observations</dt>
              <dd className="mono text-lg">{visible.length}</dd>
            </div>
            <div>
              <dt className="text-(--text-3)">Capteurs</dt>
              <dd className="mono text-lg">{sensors.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt className="text-(--text-3)">FRP max observée</dt>
              <dd className="mono text-lg">
                {frpMax === null ? '—' : `${frpMax.toLocaleString('fr-FR')} MW`}
              </dd>
            </div>
            <div>
              <dt className="text-(--text-3)">Dernière observation</dt>
              <dd className="mono text-lg">{formatInstant(effectiveAt, tz)}</dd>
            </div>
          </dl>
        )}
      </section>

      <div className="border-(--border-strong) mt-6 h-80 overflow-hidden rounded border">
        <MapView
          center={[event.location.longitude, event.location.latitude]}
          zoom={11}
          className="h-full w-full"
          ageReference={at.toISOString()}
          events={visible.map((d) => ({
            publicId: event.publicId,
            freshnessStatus: event.freshnessStatus,
            lastDetectedAt: d.acquiredAt.toISOString(),
            confidence: d.confidenceLevel === 'unknown' ? 'low' : d.confidenceLevel,
            detectionCount: 1,
            location: d.location,
            nearestMunicipalityName: null,
          }))}
        />
      </div>
      <p className="text-small text-(--text-3) mt-2 max-w-[68ch]">
        Chaque point est une observation importée à cet instant, colorée par son âge{' '}
        <strong>à l’instant rejoué</strong>, pas par son âge aujourd’hui.
      </p>

      <nav className="mt-8 flex flex-wrap items-baseline gap-6" aria-label="Navigation temporelle">
        {previous !== null && (
          <Link href={replayHref(previous)} className="underline underline-offset-4">
            ← Passage précédent
          </Link>
        )}
        {next !== null && (
          <Link href={replayHref(next)} className="underline underline-offset-4">
            Passage suivant →
          </Link>
        )}
        <Link
          href={`/evenements/${event.publicId}`}
          className="text-(--text-2) underline underline-offset-4"
        >
          Retour à la fiche
        </Link>
      </nav>

      <section className="mt-10" aria-labelledby="instants">
        <h2 id="instants" className="text-title font-bold tracking-tight">
          Passages satellitaires
        </h2>
        <p className="text-small text-(--text-2) mt-2 max-w-[58ch]">
          Chaque lien ouvre l’état reconstruit à ce passage — la même adresse s’ouvre à l’identique
          ailleurs.
        </p>
        <ol className="mt-4 space-y-1">
          {instants.map((instant) => {
            const isCurrent = effectiveAt !== null && instant.getTime() === effectiveAt.getTime();
            return (
              <li key={instant.toISOString()}>
                <Link
                  href={replayHref(instant)}
                  aria-current={isCurrent ? 'time' : undefined}
                  className={`mono text-small underline-offset-4 ${
                    isCurrent ? 'font-bold' : 'underline'
                  }`}
                >
                  {formatInstant(instant, tz)}
                </Link>
                {isCurrent && <span className="text-small text-(--text-3)"> — affiché</span>}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="mt-10" aria-labelledby="chrono">
        <h2 id="chrono" className="text-title font-bold tracking-tight">
          Chronologie connue à cet instant
        </h2>
        {visibleTimeline.length === 0 ? (
          <p className="text-(--text-2) mt-3">Aucune entrée de chronologie avant cet instant.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {visibleTimeline.map((entry) => (
              <li key={entry.id} className="text-small max-w-[58ch]">
                <span className="mono text-(--text-3)">{formatInstant(entry.occurredAt, tz)}</span>{' '}
                — {entry.title}
                {entry.summary !== null && (
                  <span className="text-(--text-2)"> · {entry.summary}</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
