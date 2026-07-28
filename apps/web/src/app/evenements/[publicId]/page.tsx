import {
  dataAgeMs,
  EVENT_DISCLAIMER,
  formatDataAge,
  isSnapshotStale,
  MAP_DISCLAIMER,
} from '@mapfeux/domain';
import { PALETTE } from '@mapfeux/map-style';
import {
  CONFIDENCE_LEVEL_LABELS,
  CONFIDENCE_LEVEL_NOTICE,
  EVENT_FRESHNESS_DESCRIPTIONS,
  OFFICIAL_CONTROL_STATUS_LABELS,
  ProvenanceBadge,
  PROVENANCE_LABELS,
  VERIFICATION_STATUS_DESCRIPTIONS,
  VERIFICATION_STATUS_LABELS,
} from '@mapfeux/ui';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, permanentRedirect } from 'next/navigation';

import { MapView } from '@/components/map/map-view';
import { ShareLink } from '@/components/share-link';
import {
  fetchEvent,
  fetchEventDetections,
  fetchEventView,
  resolveEventAlias,
  type FireEvent,
} from '@/lib/data/events';
import { fetchOfficialLinks } from '@/lib/data/territories';
import { getServerEnv } from '@/lib/env';

/**
 * Fiche événement — cahier §5.6 et §5.7.
 *
 * C'est l'objet central du produit. Trois règles gouvernent cette page :
 *
 * 1. **Elle est complète sans JavaScript.** Tout est rendu côté serveur ; la
 *    carte et le bouton de copie sont des ajouts, pas des conditions (FR-051).
 * 2. **Aucun bloc n'est affiché sans provenance ni horodatage.** Observation,
 *    calcul, estimation et information officielle sont visuellement distincts
 *    (FR-053).
 * 3. **L'absence d'information officielle est dite**, pas laissée à
 *    l'interprétation. Un événement sans statut officiel n'est pas un
 *    événement dont le statut serait « en cours ».
 */

export const revalidate = 120;

/**
 * Couleur de la pastille de chronologie selon la provenance.
 *
 * Observation, calcul et information officielle ne se confondent pas d'un
 * coup d'œil (FR-053). Le libellé reste affiché à côté : la couleur ne porte
 * jamais seule le sens (§6.5).
 */
const PROVENANCE_DOT: Record<string, string> = {
  observation: PALETTE.thermal.recent,
  algorithmic_inference: PALETTE.inference,
  model_estimate: PALETTE.inference,
  official_information: PALETTE.official,
  editorial_correction: PALETTE.neutral.strong,
  external_report: PALETTE.neutral.muted,
};

interface PageParams {
  params: Promise<{ publicId: string }>;
}

function formatInstant(value: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone,
  }).format(value);
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { publicId } = await params;
  const event = await fetchEvent(publicId);

  if (event === null) {
    return { title: 'Événement introuvable', robots: { index: false, follow: false } };
  }

  const place = event.nearestMunicipality?.name ?? event.territory?.name ?? 'France';
  const verification = VERIFICATION_STATUS_LABELS[event.verificationStatus].toLowerCase();

  return {
    title: `${event.publicId} — ${place}`,
    description: `${verification} près de ${place}. ${event.detectionCount} détection${
      event.detectionCount > 1 ? 's' : ''
    } satellitaire${event.detectionCount > 1 ? 's' : ''} entre le ${formatInstant(
      event.firstDetectedAt,
      event.timeZone,
    )} et le ${formatInstant(event.lastDetectedAt, event.timeZone)}. ${EVENT_DISCLAIMER}`,
    openGraph: {
      type: 'article',
      title: `${event.publicId} — ${place}`,
      description: EVENT_DISCLAIMER,
    },
  };
}

function StateCell({
  label,
  children,
  note,
}: {
  label: string;
  children: React.ReactNode;
  note: string;
}) {
  return (
    <div
      className="border-b p-4 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0"
      style={{ borderColor: 'var(--border)' }}
    >
      <div
        className="mono mb-2 text-[10px] uppercase tracking-[0.11em]"
        style={{ color: 'var(--text-3)' }}
      >
        {label}
      </div>
      {children}
      <p className="mt-2 text-[12.5px] leading-snug" style={{ color: 'var(--text-2)' }}>
        {note}
      </p>
    </div>
  );
}

/**
 * Les trois dimensions de statut, côte à côte et jamais fusionnées. §17.4
 *
 * La mise en grille est un choix de fond, pas de mise en page : les afficher
 * l'une sous l'autre suggérerait une hiérarchie ou une progression, là où il
 * s'agit de trois questions indépendantes.
 */
function StatusPanel({ event, now }: { event: FireEvent; now: Date }) {
  const age = formatDataAge(dataAgeMs(event.lastDetectedAt, now));

  return (
    <section
      aria-labelledby="statuts"
      className="mt-6 grid overflow-hidden rounded-2xl border md:grid-cols-3"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <h2 id="statuts" className="sr-only">
        Statuts
      </h2>

      <StateCell
        label="Fraîcheur technique"
        note={EVENT_FRESHNESS_DESCRIPTIONS[event.freshnessStatus]}
      >
        <span
          className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[13px] font-semibold"
          style={{ background: 'var(--color-age-1-wash)', color: 'var(--color-age-1)' }}
        >
          Observé il y a {age}
        </span>
      </StateCell>

      <StateCell
        label="Niveau de vérification"
        note={VERIFICATION_STATUS_DESCRIPTIONS[event.verificationStatus]}
      >
        <span
          className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[13px] font-medium"
          style={{ background: 'var(--surface-muted)', color: 'var(--text)' }}
        >
          {VERIFICATION_STATUS_LABELS[event.verificationStatus]}
        </span>
      </StateCell>

      <StateCell
        label="Statut officiel"
        note={
          event.officialSource === null
            ? 'Rien de publié sur cet événement par la préfecture ou la commune. Cela ne signifie pas qu’il n’y en a pas eu.'
            : `Publié par ${event.officialSource.organisation}.`
        }
      >
        {event.officialControlStatus === null || event.officialSource === null ? (
          // Une puce en pointillé, pas un vide : l'absence d'information
          // officielle est un fait à énoncer, qu'un blanc laisserait lire
          // comme « rien à signaler ».
          <span
            className="inline-flex items-center gap-2 rounded-full border border-dashed px-3 py-1 text-[13px]"
            style={{ borderColor: 'var(--border-strong)', color: 'var(--text-3)' }}
          >
            Aucune source officielle
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[13px] font-semibold"
            style={{
              background: 'var(--color-authority-wash)',
              color: 'var(--color-authority)',
            }}
          >
            {OFFICIAL_CONTROL_STATUS_LABELS[event.officialControlStatus]}
          </span>
        )}
      </StateCell>
    </section>
  );
}

export default async function EventPage({ params }: PageParams) {
  const { publicId } = await params;

  const view = await fetchEventView(publicId);

  if (view === null) {
    // Identifiant fusionné : redirection permanente vers l'événement canonique
    // plutôt qu'un 404. Une URL partagée ne doit jamais se périmer (§13.10).
    const canonical = await resolveEventAlias(publicId);
    if (canonical !== null && canonical !== publicId) {
      permanentRedirect(`/evenements/${canonical}`);
    }
    notFound();
  }

  const { event, timeline } = view;

  const [detections, officialLinks] = await Promise.all([
    fetchEventDetections(event.publicId),
    event.territory === null ? Promise.resolve([]) : fetchOfficialLinks(event.territory.slug),
  ]);

  const now = new Date();
  const snapshotIsStale =
    view.generatedAt !== null &&
    isSnapshotStale({
      generatedAt: view.generatedAt,
      now,
      eventFreshness: event.freshnessStatus,
    });
  const canonicalUrl = `${getServerEnv().PUBLIC_APP_URL}/evenements/${event.publicId}`;
  const isFixture = event.publicId.startsWith('DEMO-');

  return (
    <article className="mx-auto max-w-3xl px-4 py-8">
      {isFixture && (
        <p className="mb-6 rounded border-2 border-amber-500 bg-amber-50 p-4 text-sm font-medium text-amber-900">
          Jeu de démonstration. Les détections de cette page sont inventées et ne correspondent à
          aucune observation satellitaire réelle.
        </p>
      )}

      {snapshotIsStale && (
        <p className="mb-6 rounded border-2 border-orange-500 bg-orange-50 p-4 text-sm text-orange-900">
          Cette fiche affiche un état figé qui n’a pas été reconstruit depuis{' '}
          {formatDataAge(dataAgeMs(view.generatedAt as Date, now))}, alors que cet événement reçoit
          habituellement des observations plus fréquentes. Les informations ci-dessous peuvent être
          en retard sur la situation.
        </p>
      )}

      <nav aria-label="Fil d’Ariane" className="text-sm text-stone-600">
        <Link href="/" className="underline underline-offset-4">
          Accueil
        </Link>
        {event.territory !== null && (
          <>
            {' / '}
            <Link
              href={`/territoire/${event.territory.slug}`}
              className="underline underline-offset-4"
            >
              {event.territory.name}
            </Link>
          </>
        )}
      </nav>

      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        {event.nearestMunicipality === null
          ? 'Événement thermique'
          : `Événement thermique près de ${event.nearestMunicipality.name}`}
      </h1>
      <p className="mt-1 font-mono text-sm text-stone-600">{event.publicId}</p>

      <StatusPanel event={event} now={now} />

      {/* Dernière observation : l'horodatage exact accompagne toujours l'âge. */}
      <section aria-labelledby="derniere-observation" className="mt-8">
        <h2 id="derniere-observation" className="text-xl font-semibold">
          Dernière observation
        </h2>
        <p className="mt-2">
          <time dateTime={event.lastDetectedAt.toISOString()} className="text-lg">
            {formatInstant(event.lastDetectedAt, event.timeZone)}
          </time>
          <span className="ml-2 text-stone-600">
            (il y a {formatDataAge(dataAgeMs(event.lastDetectedAt, now))})
          </span>
        </p>
        <ProvenanceBadge provenance="observation" className="mt-2" />
      </section>

      {/* Synthèse. Chaque chiffre est une agrégation, donc un calcul. */}
      <section aria-labelledby="synthese" className="mt-8">
        <h2 id="synthese" className="text-xl font-semibold">
          Synthèse
        </h2>
        <ProvenanceBadge provenance="algorithmic_inference" className="mt-2" />

        <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-stone-600">Première observation</dt>
            <dd>
              <time dateTime={event.firstDetectedAt.toISOString()}>
                {formatInstant(event.firstDetectedAt, event.timeZone)}
              </time>
            </dd>
          </div>
          <div>
            <dt className="text-sm text-stone-600">Détections</dt>
            <dd>
              {event.detectionCount} sur {event.sensorCount} capteur
              {event.sensorCount > 1 ? 's' : ''}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-stone-600">Capteurs</dt>
            <dd>{event.sensors.length === 0 ? '—' : event.sensors.join(', ')}</dd>
          </div>
          <div>
            <dt className="text-sm text-stone-600">Satellites</dt>
            <dd>{event.satellites.length === 0 ? '—' : event.satellites.join(', ')}</dd>
          </div>
          <div>
            <dt className="text-sm text-stone-600">Puissance radiative (FRP)</dt>
            <dd>
              {event.frp.median === null
                ? 'Non disponible'
                : `médiane ${event.frp.median} MW, maximum ${event.frp.max ?? '—'} MW`}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-stone-600">Fiabilité</dt>
            <dd>{CONFIDENCE_LEVEL_LABELS[event.confidenceLevel]}</dd>
          </div>
        </dl>

        <p className="mt-3 text-xs text-stone-600">{CONFIDENCE_LEVEL_NOTICE}</p>
      </section>

      {/* Chronologie triée par heure de survenue, pas d'import. FR-055 */}
      <section aria-labelledby="chronologie" className="mt-10">
        <h2 id="chronologie" className="text-xl font-semibold">
          Chronologie
        </h2>
        {timeline.length === 0 ? (
          <p className="mt-2 text-stone-700">Aucune entrée de chronologie pour cet événement.</p>
        ) : (
          <ol className="relative mt-4 pl-6">
            {/* Filet vertical : la chronologie se lit comme une ligne de temps,
                les pastilles portant la provenance de chaque entrée. */}
            <span
              aria-hidden="true"
              className="absolute bottom-1.5 left-1 top-1.5 w-px"
              style={{ background: 'var(--border)' }}
            />
            {timeline.map((entry) => (
              <li key={entry.id} className="relative pb-5 last:pb-0">
                <span
                  aria-hidden="true"
                  className="absolute -left-6 top-1.5 block size-2.5 rounded-full border-2"
                  style={{
                    background: PROVENANCE_DOT[entry.provenance],
                    borderColor: 'var(--surface)',
                  }}
                />
                <p className="text-sm leading-snug">{entry.title}</p>
                {entry.summary !== null && (
                  <p className="mt-1 text-sm" style={{ color: 'var(--text-2)' }}>
                    {entry.summary}
                  </p>
                )}
                <p
                  className="mono mt-1 text-[11px]"
                  style={{ color: PROVENANCE_DOT[entry.provenance] }}
                >
                  <time dateTime={entry.occurredAt.toISOString()}>
                    {formatInstant(entry.occurredAt, event.timeZone)}
                  </time>{' '}
                  · {PROVENANCE_LABELS[entry.provenance].toLowerCase()}
                  {entry.source !== null && (
                    <>
                      {' · '}
                      <a href={entry.source.url} rel="noopener noreferrer" className="underline">
                        {entry.source.organisation}
                      </a>
                    </>
                  )}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Alternative textuelle à la carte. §8.6 */}
      <section aria-labelledby="detections" className="mt-10">
        <h2 id="detections" className="text-xl font-semibold">
          Détections membres
        </h2>
        <p className="mt-2 text-sm text-stone-700">{MAP_DISCLAIMER}</p>

        {detections.length === 0 ? (
          <p className="mt-3 text-stone-700">Aucune détection publiable.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-xl w-full border-collapse text-left text-sm">
              <caption className="sr-only">
                Détections satellitaires rattachées à cet événement, de la plus récente à la plus
                ancienne
              </caption>
              <thead>
                <tr className="border-b-2 border-stone-300">
                  <th scope="col" className="py-2 pr-4">
                    Heure d’acquisition
                  </th>
                  <th scope="col" className="py-2 pr-4">
                    Capteur
                  </th>
                  <th scope="col" className="py-2 pr-4">
                    Confiance
                  </th>
                  <th scope="col" className="py-2">
                    FRP
                  </th>
                </tr>
              </thead>
              <tbody>
                {detections.map((detection) => (
                  <tr
                    key={`${detection.acquiredAt.toISOString()}-${detection.location.longitude}`}
                    className="border-b border-stone-200"
                  >
                    <td className="py-2 pr-4">
                      <time dateTime={detection.acquiredAt.toISOString()}>
                        {formatInstant(detection.acquiredAt, event.timeZone)}
                      </time>
                    </td>
                    <td className="py-2 pr-4">
                      {detection.sensor} · {detection.satellite}
                      {detection.dayNight !== null && (
                        <span className="text-stone-600">
                          {detection.dayNight === 'D' ? ' · jour' : ' · nuit'}
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {detection.confidenceLevel === 'unknown'
                        ? 'Inconnue'
                        : CONFIDENCE_LEVEL_LABELS[detection.confidenceLevel]}
                    </td>
                    <td className="py-2">
                      {detection.frpMw === null ? '—' : `${detection.frpMw} MW`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* La carte vient après le contenu : elle l'illustre, ne le porte pas. */}
      <section aria-labelledby="localisation" className="mt-10">
        <h2 id="localisation" className="text-xl font-semibold">
          Localisation
        </h2>
        <p className="mt-2 text-sm text-stone-700">
          Position représentative : {event.location.latitude.toFixed(4)} N,{' '}
          {event.location.longitude.toFixed(4)} E
          {event.nearestMunicipality !== null && (
            <>
              {' · commune la plus proche : '}
              <Link
                href={`/commune/${event.nearestMunicipality.insee}`}
                className="underline underline-offset-4"
              >
                {event.nearestMunicipality.name}
              </Link>
            </>
          )}
        </p>
        <div className="mt-3 h-72 overflow-hidden rounded border border-stone-300">
          <MapView
            center={[event.location.longitude, event.location.latitude]}
            zoom={11}
            className="h-full w-full"
          />
        </div>
      </section>

      {/* Ce qui n'est pas affiché, et pourquoi. Une absence non expliquée se lit
          comme une absence de phénomène. */}
      <section aria-labelledby="non-disponible" className="mt-10 rounded bg-stone-100 p-4">
        <h2 id="non-disponible" className="text-lg font-semibold">
          Ce que cette fiche ne montre pas
        </h2>
        <p className="mt-2 text-sm text-stone-800">
          Le panache de fumée indicatif, les communes potentiellement concernées et la qualité de
          l’air ne sont pas publiés. Un panache estimé à partir du vent au sol est trop incertain en
          relief pour être affiché sans induire en erreur. Ces fonctions reviendront lorsqu’un vent
          de transport en altitude et une calibration sur cas connus seront disponibles.
        </p>
      </section>

      {officialLinks.length > 0 && (
        <section aria-labelledby="officiel" className="mt-10">
          <h2 id="officiel" className="text-xl font-semibold">
            Informations officielles du territoire
          </h2>
          <ul className="mt-3 space-y-2">
            {officialLinks.map((link) => (
              <li key={link.url}>
                <a
                  href={link.url}
                  rel="noopener noreferrer"
                  className="underline underline-offset-4"
                >
                  {link.title}
                </a>
                <span className="block text-xs text-stone-600">{link.organisation}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="partage" className="mt-10">
        <h2 id="partage" className="text-xl font-semibold">
          Partager
        </h2>
        <p className="mt-2 text-sm">
          URL permanente :{' '}
          <a href={canonicalUrl} className="break-all underline underline-offset-4">
            {canonicalUrl}
          </a>
        </p>
        <p className="mt-3">
          <ShareLink url={canonicalUrl} />
        </p>
      </section>

      <footer className="mt-10 border-t border-stone-200 pt-4 text-xs text-stone-600">
        <p>{EVENT_DISCLAIMER}</p>
        {/* Les trois horodatages sont distincts et tous affichés : l'heure de
            consultation, celle de la construction de l'état, et celle de la
            donnée elle-même. Les confondre laisserait croire qu'une page
            fraîchement servie porte une observation fraîche (§21.5). */}
        <p className="mt-2">
          Page servie le{' '}
          <time dateTime={now.toISOString()}>{formatInstant(now, event.timeZone)}</time>.
          {view.generatedAt === null ? (
            <> État lu directement en base, sans état figé disponible.</>
          ) : (
            <>
              {' '}
              État figé construit le{' '}
              <time dateTime={view.generatedAt.toISOString()}>
                {formatInstant(view.generatedAt, event.timeZone)}
              </time>
              .
            </>
          )}{' '}
          Donnée la plus récente :{' '}
          <time dateTime={event.lastDetectedAt.toISOString()}>
            {formatInstant(event.lastDetectedAt, event.timeZone)}
          </time>
          .
        </p>
        <p className="mt-2">
          <Link href="/methodologie" className="underline underline-offset-4">
            Méthodologie
          </Link>
          {' · '}
          <Link href="/sources" className="underline underline-offset-4">
            Sources et licences
          </Link>
        </p>
      </footer>
    </article>
  );
}
