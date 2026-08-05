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

/**
 * Couleurs de l'état d'une source.
 *
 * Aucun vert : « à jour » se lit à la sobriété, pas à une pastille rassurante.
 * Le registre chaud reste réservé aux phénomènes thermiques (§8.2) ; un retard
 * de source emprunte l'ambre de `degraded`, qui décrit l'état de la donnée et
 * non celui du terrain.
 */
const FRESHNESS_STYLES: Record<string, { background: string; color: string }> = {
  fresh: { background: 'var(--surface-muted)', color: 'var(--text)' },
  delayed: { background: 'var(--color-degraded-wash)', color: 'var(--color-degraded)' },
  stale: { background: 'var(--color-degraded-wash)', color: 'var(--color-degraded)' },
  unavailable: { background: 'var(--surface-muted)', color: 'var(--text-3)' },
  maintenance: { background: 'var(--color-authority-wash)', color: 'var(--color-authority)' },
  // « À venir » se lit en retrait, comme une note et non comme un état : une
  // source qui n'existe pas encore n'a pas à occuper l'œil autant qu'une
  // source tombée.
  upcoming: { background: 'var(--surface-muted)', color: 'var(--text-3)' },
};

function SourceRow({ source, now }: { source: SourceStatusRow; now: Date }) {
  const dataAt = source.last_data_at === null ? null : new Date(source.last_data_at);

  return (
    <tr className="border-b align-top" style={{ borderColor: 'var(--border)' }}>
      <th scope="row" className="py-3 pr-4 text-left font-medium">
        {source.name}
        <span className="block text-xs font-normal" style={{ color: 'var(--text-3)' }}>
          {source.provider}
        </span>
      </th>
      <td className="py-3 pr-4">
        <span
          className="inline-block rounded-full px-3 py-1 text-xs font-medium"
          style={FRESHNESS_STYLES[source.freshness] ?? FRESHNESS_STYLES['unavailable']}
        >
          {SOURCE_FRESHNESS_LABELS[source.freshness]}
        </span>
      </td>
      <td className="py-3 pr-4 text-sm">
        {dataAt === null ? (
          <span style={{ color: 'var(--text-3)' }}>Aucune donnée</span>
        ) : (
          <>
            <time dateTime={dataAt.toISOString()}>
              {new Intl.DateTimeFormat('fr-FR', {
                dateStyle: 'short',
                timeStyle: 'short',
                timeZone: 'Europe/Paris',
              }).format(dataAt)}
            </time>
            <span className="block text-xs" style={{ color: 'var(--text-3)' }}>
              il y a {formatDataAge(Math.max(0, now.getTime() - dataAt.getTime()))}
            </span>
          </>
        )}
      </td>
      <td className="py-3 text-sm">
        {source.incident_message === null ? (
          <span style={{ color: 'var(--text-3)' }}>—</span>
        ) : (
          <span style={{ color: 'var(--color-degraded)' }}>{source.incident_message}</span>
        )}
      </td>
    </tr>
  );
}

export default async function StatusPage() {
  const result = await fetchSourceStatus();
  const sources = result.sources;
  const now = new Date();

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">État des données</h1>
      <p className="mt-3 max-w-2xl" style={{ color: 'var(--text-2)' }}>
        Chaque source est indépendante. L’indisponibilité de l’une n’empêche pas l’affichage des
        autres : les couches concernées sont signalées comme indisponibles plutôt que masquées
        silencieusement.
      </p>

      {!result.readable ? (
        <p
          className="mt-8 rounded-xl border p-4 text-sm"
          style={{ background: 'var(--surface-muted)', borderColor: 'var(--border)' }}
        >
          L’état des sources n’est pas consultable actuellement. Cette page ne reflète donc pas la
          situation réelle des imports.
        </p>
      ) : sources.length === 0 ? (
        <p
          className="mt-8 rounded-xl border p-4 text-sm"
          style={{ background: 'var(--surface-muted)', borderColor: 'var(--border)' }}
        >
          Aucune source de données n’est encore enregistrée sur cette instance.
        </p>
      ) : (
        <div className="mt-8 overflow-x-auto">
          <table className="min-w-xl w-full border-collapse text-left">
            <caption className="sr-only">
              Fraîcheur des sources de données, dernière donnée disponible et incidents en cours
            </caption>
            <thead>
              <tr className="border-b-2 text-sm" style={{ borderColor: 'var(--border-strong)' }}>
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

      <p className="mt-8 text-xs" style={{ color: 'var(--text-3)' }}>
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
