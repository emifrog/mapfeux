import type { Metadata } from 'next';
import Link from 'next/link';

import { EventList } from '@/components/event-list';
import { decodeCatalogCursor, fetchEventsCatalog, type CatalogFilters } from '@/lib/data/events';

/**
 * Archives des événements. Cahier FR-048 et FR-053.
 *
 * Un événement archivé est sorti de la fenêtre d'affichage courant — sept
 * jours sans nouvelle observation (cycle-de-vie-v1). Ce n'est **pas** une
 * conclusion sur l'extinction : le vocabulaire de la page le dit, la donnée
 * ne le sait pas.
 *
 * Même mécanique que le catalogue : rendu serveur, filtres en GET, pagination
 * par curseur — tout fonctionne sans JavaScript.
 */

export const metadata: Metadata = {
  title: 'Archives',
  description:
    'Événements thermiques sortis de la fenêtre courante, consultables par département, avec pagination.',
};

const DEPARTMENT_PATTERN = /^(\d{2}|2[ab])$/i;

function firstValue(value: string | string[] | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

export default async function ArchivesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;

  const rawDepartment = firstValue(params['departement'])?.trim() ?? '';
  const department = DEPARTMENT_PATTERN.test(rawDepartment)
    ? rawDepartment.toUpperCase()
    : undefined;

  const rawCursor = firstValue(params['curseur']);
  const cursor = rawCursor === undefined ? undefined : decodeCatalogCursor(rawCursor);

  const filters: CatalogFilters = {
    freshness: 'archived',
    limit: 50,
    ...(department === undefined ? {} : { department }),
    ...(cursor == null ? {} : { cursor }),
  };
  const { events, nextCursor } = await fetchEventsCatalog(filters);
  const now = new Date();

  const baseQuery = new URLSearchParams();
  if (department !== undefined) baseQuery.set('departement', department);
  const nextQuery = new URLSearchParams(baseQuery);
  if (nextCursor !== null) nextQuery.set('curseur', nextCursor);

  return (
    <div className="shell max-w-[75ch] py-14">
      <p className="eyebrow mb-3">archives</p>
      <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Événements archivés
      </h1>
      <p className="text-lead text-(--text-2) mt-4 max-w-[58ch]">
        Événements sans nouvelle observation depuis plus de sept jours, sortis de la fenêtre
        courante. L’archivage est un état technique : il ne dit pas qu’un feu est éteint.
      </p>
      <p className="text-small text-(--text-2) mt-3">
        Les événements récents restent dans le{' '}
        <Link href="/evenements" className="underline underline-offset-4">
          catalogue
        </Link>
        .
      </p>

      <form method="get" action="/archives" className="mt-8 flex flex-wrap items-end gap-4">
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
        <button
          type="submit"
          className="border-(--border-strong) rounded border px-4 py-2 font-semibold"
        >
          Filtrer
        </button>
      </form>

      <section className="mt-10" aria-label="Liste des événements archivés">
        {events.length === 0 ? (
          <p className="text-(--text-2) max-w-[68ch]">
            Aucun événement archivé ne correspond à ce filtre. Les archives se remplissent au fil du
            temps, à mesure que des événements sortent de la fenêtre courante.
          </p>
        ) : (
          <EventList events={events} now={now} />
        )}
      </section>

      <nav className="mt-10 flex items-baseline gap-6" aria-label="Pagination">
        {cursor != null && (
          <Link
            href={`/archives${baseQuery.size > 0 ? `?${baseQuery.toString()}` : ''}`}
            className="underline underline-offset-4"
          >
            ← Revenir aux plus récentes
          </Link>
        )}
        {nextCursor !== null && (
          <Link href={`/archives?${nextQuery.toString()}`} className="underline underline-offset-4">
            Archives plus anciennes →
          </Link>
        )}
      </nav>
    </div>
  );
}
