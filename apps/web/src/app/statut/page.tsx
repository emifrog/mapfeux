import { formatDataAge } from '@mapfeux/domain';
import { SOURCE_FRESHNESS_LABELS } from '@mapfeux/ui';
import type { Metadata } from 'next';

import { fetchSourceStatus, type SourceStatusRow } from '@/lib/sources';

/**
 * Page /statut — cahier §5.13.
 *
 * FR-110 : chaque source, son dernier import réussi, sa dernière donnée et ses
 * incidents. FR-112 : le public reçoit un message compréhensible, jamais la
 * trace technique. FR-115 : aucun chargement indéfini — la page est rendue
 * côté serveur et affiche l'indisponibilité plutôt que d'attendre.
 */

export const metadata: Metadata = {
  title: 'État des données',
  description:
    'Fraîcheur de chaque source de données utilisée par MapFeux : détections satellitaires, météo, qualité de l’air et radar.',
};

// La fraîcheur des sources change à chaque import : pas de mise en cache longue.
export const revalidate = 60;

const FRESHNESS_STYLES: Record<string, string> = {
  fresh: 'bg-emerald-50 text-emerald-900 border-emerald-300',
  delayed: 'bg-amber-50 text-amber-900 border-amber-300',
  stale: 'bg-orange-50 text-orange-900 border-orange-300',
  unavailable: 'bg-stone-100 text-stone-900 border-stone-400',
  maintenance: 'bg-sky-50 text-sky-900 border-sky-300',
};

function SourceRow({ source, now }: { source: SourceStatusRow; now: Date }) {
  const dataAt = source.last_data_at === null ? null : new Date(source.last_data_at);

  return (
    <tr className="border-b border-stone-200 align-top">
      <th scope="row" className="py-3 pr-4 text-left font-medium">
        {source.name}
        <span className="block text-xs font-normal text-stone-500">{source.provider}</span>
      </th>
      <td className="py-3 pr-4">
        <span
          className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${
            FRESHNESS_STYLES[source.freshness] ?? FRESHNESS_STYLES.unavailable
          }`}
        >
          {SOURCE_FRESHNESS_LABELS[source.freshness]}
        </span>
      </td>
      <td className="py-3 pr-4 text-sm">
        {dataAt === null ? (
          <span className="text-stone-500">Aucune donnée</span>
        ) : (
          <>
            <time dateTime={dataAt.toISOString()}>
              {new Intl.DateTimeFormat('fr-FR', {
                dateStyle: 'short',
                timeStyle: 'short',
                timeZone: 'Europe/Paris',
              }).format(dataAt)}
            </time>
            <span className="block text-xs text-stone-500">
              il y a {formatDataAge(Math.max(0, now.getTime() - dataAt.getTime()))}
            </span>
          </>
        )}
      </td>
      <td className="py-3 text-sm">
        {source.incident_message === null ? (
          <span className="text-stone-500">—</span>
        ) : (
          <span className="text-orange-900">{source.incident_message}</span>
        )}
      </td>
    </tr>
  );
}

export default async function StatusPage() {
  const sources = await fetchSourceStatus();
  const now = new Date();

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">État des données</h1>
      <p className="mt-3 max-w-2xl text-stone-700">
        Chaque source est indépendante. L’indisponibilité de l’une n’empêche pas l’affichage des
        autres : les couches concernées sont signalées comme indisponibles plutôt que masquées
        silencieusement.
      </p>

      {sources.length === 0 ? (
        <p className="mt-8 rounded border border-stone-400 bg-stone-100 p-4 text-sm">
          L’état des sources n’est pas consultable actuellement. Cette page ne reflète donc pas la
          situation réelle des imports.
        </p>
      ) : (
        <div className="mt-8 overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-left">
            <caption className="sr-only">
              Fraîcheur des sources de données, dernière donnée disponible et incidents en cours
            </caption>
            <thead>
              <tr className="border-b-2 border-stone-300 text-sm">
                <th scope="col" className="py-2 pr-4">
                  Source
                </th>
                <th scope="col" className="py-2 pr-4">
                  État
                </th>
                <th scope="col" className="py-2 pr-4">
                  Dernière donnée
                </th>
                <th scope="col" className="py-2">
                  Incident
                </th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <SourceRow key={source.key} source={source} now={now} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-8 text-xs text-stone-500">
        Page générée le{' '}
        <time dateTime={now.toISOString()}>
          {new Intl.DateTimeFormat('fr-FR', {
            dateStyle: 'long',
            timeStyle: 'medium',
            timeZone: 'Europe/Paris',
          }).format(now)}
        </time>
        .
      </p>
    </div>
  );
}
