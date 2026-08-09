import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';

import { EventList } from '@/components/event-list';
import { MapView } from '@/components/map/map-view';
import { decodeCatalogCursor, fetchEventsCatalog, type CatalogFilters } from '@/lib/data/events';

/**
 * Catalogue national des événements. Cahier FR-050 à FR-055.
 *
 * Rendu côté serveur : la liste, les filtres et la pagination fonctionnent
 * sans JavaScript (FR-054) — le formulaire est un GET, le curseur un lien. La
 * carte montre la page courante et les agrégats départementaux ; la liste
 * reste la vue de référence.
 *
 * Le tri est la dernière observation (FR-052). Aucun classement par
 * « importance » : aucune règle sourcée ne la définit (FR-055).
 */

export const metadata: Metadata = {
  title: 'Événements',
  description:
    'Catalogue national des événements thermiques détectés par satellite, filtrable par période, département et niveau de vérification.',
};

const PERIODS: Record<string, { label: string; hours: number }> = {
  '6h': { label: '6 heures', hours: 6 },
  '12h': { label: '12 heures', hours: 12 },
  '24h': { label: '24 heures', hours: 24 },
  '48h': { label: '48 heures', hours: 48 },
  '7j': { label: '7 jours', hours: 168 },
};

const DEFAULT_PERIOD = '7j';

const VERIFICATIONS: Record<string, string> = {
  satellite_detection: 'Détection satellitaire',
  probable_event: 'Événement probable',
  publicly_reported: 'Signalé publiquement',
  officially_confirmed: 'Confirmé officiellement',
};

const DEPARTMENT_PATTERN = /^(\d{2}|2[ab])$/i;

const FRANCE_CENTER: readonly [number, number] = [2.55, 46.6];

function firstValue(value: string | string[] | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

export default async function EventsCatalogPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;

  const periodKey = firstValue(params['periode']) ?? DEFAULT_PERIOD;
  const period = PERIODS[periodKey] ?? PERIODS[DEFAULT_PERIOD];

  const rawDepartment = firstValue(params['departement'])?.trim() ?? '';
  const department = DEPARTMENT_PATTERN.test(rawDepartment)
    ? rawDepartment.toUpperCase()
    : undefined;

  const rawVerification = firstValue(params['verification']) ?? '';
  const verification = rawVerification in VERIFICATIONS ? rawVerification : undefined;

  const rawCursor = firstValue(params['curseur']);
  const cursor = rawCursor === undefined ? undefined : decodeCatalogCursor(rawCursor);

  const now = new Date();
  const since = new Date(now.getTime() - (period?.hours ?? 168) * 3_600_000);

  const filters: CatalogFilters = {
    since,
    limit: 50,
    ...(department === undefined ? {} : { department }),
    ...(verification === undefined ? {} : { verification }),
    ...(cursor == null ? {} : { cursor }),
  };
  const { events, nextCursor } = await fetchEventsCatalog(filters);

  // Les liens de pagination conservent les filtres : un curseur sans sa
  // période paginerait un autre catalogue que celui affiché.
  const baseQuery = new URLSearchParams();
  if (periodKey !== DEFAULT_PERIOD && PERIODS[periodKey] !== undefined) {
    baseQuery.set('periode', periodKey);
  }
  if (department !== undefined) baseQuery.set('departement', department);
  if (verification !== undefined) baseQuery.set('verification', verification);
  const nextQuery = new URLSearchParams(baseQuery);
  if (nextCursor !== null) nextQuery.set('curseur', nextCursor);

  const generatedAt = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Europe/Paris',
  }).format(now);

  return (
    <div className="shell py-14">
      <div className="max-w-[68ch]">
        <p className="eyebrow mb-3">catalogue national</p>
        <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
          Événements
        </h1>
        <p className="text-lead text-(--text-2) mt-4">
          Tous les événements déduits des détections satellitaires, triés par dernière observation.
          Page établie le {generatedAt}.
        </p>
        <p className="text-small text-(--text-2) mt-3">
          Les événements sortis de la fenêtre courante sont dans les{' '}
          <Link href="/archives" className="underline underline-offset-4">
            archives
          </Link>
          .
        </p>
      </div>

      <form method="get" action="/evenements" className="mt-8 flex flex-wrap items-end gap-4">
        <label className="block">
          <span className="block text-sm font-medium">Période</span>
          <select
            name="periode"
            defaultValue={periodKey in PERIODS ? periodKey : DEFAULT_PERIOD}
            className="border-(--border-strong) mt-1 rounded border px-3 py-2 text-base"
          >
            {Object.entries(PERIODS).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Département</span>
          <input
            name="departement"
            defaultValue={department ?? ''}
            placeholder="06, 2A…"
            pattern="([0-9]{2}|2[ABab])"
            className="border-(--border-strong) mt-1 w-24 rounded border px-3 py-2 text-base"
          />
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Niveau de vérification</span>
          <select
            name="verification"
            defaultValue={verification ?? ''}
            className="border-(--border-strong) mt-1 rounded border px-3 py-2 text-base"
          >
            <option value="">Tous</option>
            {Object.entries(VERIFICATIONS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="submit"
          className="border-(--border-strong) rounded border px-4 py-2 font-semibold"
        >
          Filtrer
        </button>
      </form>

      <div
        className="mt-8 h-96 overflow-hidden rounded-lg border"
        style={{ borderColor: 'var(--border-strong)' }}
      >
        <MapView
          center={FRANCE_CENTER}
          zoom={5}
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
        />
      </div>
      <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">{MAP_DISCLAIMER}</p>

      <section className="mt-10 max-w-[75ch]" aria-label="Liste des événements">
        {events.length === 0 ? (
          <p className="text-(--text-2) max-w-[68ch]">
            Aucun événement ne correspond à ces filtres sur la période. Cela ne signifie pas qu’il
            ne se passe rien : une détection récente peut ne pas encore être importée, et l’
            <Link href="/statut" className="underline underline-offset-4">
              état des données
            </Link>{' '}
            indique depuis quand la donnée date.
          </p>
        ) : (
          <EventList events={events} now={now} />
        )}
      </section>

      <nav className="mt-10 flex items-baseline gap-6" aria-label="Pagination">
        {cursor != null && (
          <Link
            href={`/evenements${baseQuery.size > 0 ? `?${baseQuery.toString()}` : ''}`}
            className="underline underline-offset-4"
          >
            ← Revenir aux plus récents
          </Link>
        )}
        {nextCursor !== null && (
          <Link
            href={`/evenements?${nextQuery.toString()}`}
            className="underline underline-offset-4"
          >
            Événements plus anciens →
          </Link>
        )}
      </nav>
    </div>
  );
}
