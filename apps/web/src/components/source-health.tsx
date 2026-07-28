import { dataAgeMs, formatDataAge } from '@mapfeux/domain';

import { fetchSourceStatus } from '@/lib/sources';

/**
 * Pastille de santé des sources, présente sur toutes les pages.
 *
 * Référence : cahier §8.1 et FR-005.
 *
 * L'utilisateur doit comprendre l'état de fraîcheur sans ouvrir de page
 * secondaire. La pastille dit trois choses et pas une de plus : combien de
 * sources répondent, sur combien, et depuis quand date la donnée la plus
 * récente. Elle ne résume jamais en un mot du type « opérationnel », qui
 * masquerait qu'une source structurante est tombée.
 */
export async function SourceHealth() {
  const result = await fetchSourceStatus();

  if (!result.readable) {
    return (
      <span
        className="mono flex items-center gap-2 rounded-full border px-3 py-1 text-[11.5px]"
        style={{
          background: 'var(--color-degraded-wash)',
          borderColor: 'var(--border)',
          color: 'var(--text-2)',
        }}
      >
        <i
          aria-hidden="true"
          className="block size-[7px] shrink-0 rounded-full"
          style={{ background: 'var(--color-degraded)' }}
        />
        état des sources inconnu
      </span>
    );
  }

  const total = result.sources.length;
  const healthy = result.sources.filter((source) => source.freshness === 'fresh').length;

  const timestamps = result.sources
    .map((source) => source.last_data_at)
    .filter((value): value is string => value !== null)
    .map((value) => new Date(value));
  const mostRecent =
    timestamps.length === 0
      ? null
      : timestamps.reduce((latest, current) => (current > latest ? current : latest));

  const allHealthy = healthy === total && total > 0;

  return (
    <span
      className="mono flex items-center gap-2 rounded-full border px-3 py-1 text-[11.5px]"
      style={{
        background: allHealthy ? 'var(--surface-muted)' : 'var(--color-degraded-wash)',
        borderColor: 'var(--border)',
        color: 'var(--text-2)',
      }}
    >
      <i
        aria-hidden="true"
        className="block size-[7px] shrink-0 rounded-full"
        style={{ background: allHealthy ? 'var(--color-carto)' : 'var(--color-degraded)' }}
      />
      {healthy} source{healthy > 1 ? 's' : ''} sur {total}
      {mostRecent !== null && <> · maj il y a {formatDataAge(dataAgeMs(mostRecent, new Date()))}</>}
    </span>
  );
}
