import { dataAgeMs, formatDataAge, isInService } from '@mapfeux/domain';

import { fetchSourceStatus } from '@/lib/sources';

/**
 * Pastille de santé des sources, présente sur toutes les pages.
 *
 * Référence : cahier §8.1, FR-005 et FR-150.
 *
 * L'utilisateur doit comprendre l'état de fraîcheur sans ouvrir de page
 * secondaire. La pastille dit trois choses et pas une de plus : combien de
 * sources répondent, sur combien, et depuis quand date la donnée la plus
 * récente. Elle ne résume jamais en un mot du type « opérationnel », qui
 * masquerait qu'une source structurante est tombée.
 *
 * ## Le décompte porte sur les sources **en service**
 *
 * Le registre déclare six sources ; deux n'ont jamais été construites. Les
 * compter donnait « 1 source sur 6 » sur toutes les pages — un service qui
 * s'annonce cassé à 83 % alors qu'il est inachevé, ce qui est aussi trompeur
 * que l'inverse.
 *
 * Les sources à venir et en maintenance sortent donc des **deux** termes du
 * ratio. Les laisser au seul dénominateur creuserait le rapport sans qu'aucune
 * panne existe. Elles restent intégralement listées sur /statut, chacune avec
 * son qualificatif : on qualifie, on ne masque pas (FR-150).
 */
export async function SourceHealth() {
  const result = await fetchSourceStatus();

  if (!result.readable) {
    return (
      <span
        className="mono text-label flex items-center gap-2 rounded-full border px-3 py-1"
        style={{
          background: 'var(--color-degraded-wash)',
          borderColor: 'var(--border)',
          color: 'var(--text-2)',
        }}
      >
        <i
          aria-hidden="true"
          className="size-1.75 block shrink-0 rounded-full"
          style={{ background: 'var(--color-degraded)' }}
        />
        état des sources inconnu
      </span>
    );
  }

  const inService = result.sources.filter((source) => isInService(source.freshness));
  const total = inService.length;
  const healthy = inService.filter((source) => source.freshness === 'fresh').length;

  // La fraîcheur affichée est celle des sources en service. Une source à venir
  // n'a par définition aucune donnée, et une source en maintenance en a de
  // vieilles : ni l'une ni l'autre ne renseigne sur ce que le site montre.
  const timestamps = inService
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
      className="mono text-label flex items-center gap-2 rounded-full border px-3 py-1"
      style={{
        background: allHealthy ? 'var(--surface-muted)' : 'var(--color-degraded-wash)',
        borderColor: 'var(--border)',
        color: 'var(--text-2)',
      }}
    >
      <i
        aria-hidden="true"
        className="size-1.75 block shrink-0 rounded-full"
        style={{ background: allHealthy ? 'var(--color-carto)' : 'var(--color-degraded)' }}
      />
      {healthy}/{total} source{total > 1 ? 's' : ''} en service
      {mostRecent !== null && <> · maj il y a {formatDataAge(dataAgeMs(mostRecent, new Date()))}</>}
    </span>
  );
}
