import { earliestUpcoming, formatDataRecency, isInService, mostRecentPast } from '@mapfeux/domain';

import { fetchSourceStatus } from '@/lib/sources';

/**
 * Pastille de santé des sources, présente sur toutes les pages.
 *
 * Référence : cahier §8.1, FR-005 et FR-150.
 *
 * L'utilisateur doit comprendre l'état de fraîcheur sans ouvrir de page
 * secondaire. La pastille dit quatre choses et pas une de plus : combien de
 * sources répondent, sur combien, depuis quand date la donnée la plus
 * récente, et **quand la prochaine est attendue**. Elle ne résume jamais en
 * un mot du type « opérationnel », qui masquerait qu'une source
 * structurante est tombée.
 *
 * ## L'échéance est une attente, pas une prédiction
 *
 * « Prochaine vers 21:16 » vient du registre — dernière donnée reçue plus
 * l'`expected_interval` déclaré, celui-là même qui sert à qualifier une
 * source de `delayed`. MapFeux ne calcule aucune orbite et ne le laisse pas
 * croire : le mot « vers » porte l'approximation, et une échéance déjà
 * dépassée n'est pas affichée — le retard se lit sur la pastille et sur
 * /statut, « prochaine il y a deux heures » n'apprendrait rien.
 *
 * L'heure est **absolue** et non relative : la page est mise en cache, et
 * une durée y vieillit mal là où une heure reste vraie.
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
const NEXT_DATA_TIME = new Intl.DateTimeFormat('fr-FR', {
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

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
  //
  // Une donnée horodatée **en avance** est écartée du concours : elle ferait
  // dire « maj il y a moins d'une minute » en permanence, et toujours par la
  // même source. Voir `mostRecentPast`.
  const now = new Date();
  const mostRecent = mostRecentPast(
    inService.map((source) =>
      source.last_data_at === null ? null : new Date(source.last_data_at),
    ),
    now,
  );

  // Par symétrie avec la fraîcheur — la donnée la plus récente de toutes
  // les sources en service —, on retient l'échéance la plus proche : le
  // moment où quelque chose bougera.
  const nextData = earliestUpcoming(
    inService.map((source) =>
      source.next_data_expected_at === null ? null : new Date(source.next_data_expected_at),
    ),
    now,
  );

  const allHealthy = healthy === total && total > 0;

  return (
    <span
      className="mono text-label flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-full border px-3 py-1"
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
      {/* Chaque mention est un seul élément de la rangée flex, insécable :
          sur un écran étroit la pastille passe à la ligne **entre** les
          mentions et jamais au milieu de l'une d'elles — sans quoi l'heure,
          qui est un élément à part entière, se détachait de « prochaine
          vers » et flottait seule à droite (constaté en 375 px). */}
      <span className="whitespace-nowrap">
        {healthy}/{total} source{total > 1 ? 's' : ''} en service
      </span>
      {mostRecent !== null && (
        <span className="whitespace-nowrap">· maj {formatDataRecency(mostRecent, now)}</span>
      )}
      {nextData !== null && (
        <span className="whitespace-nowrap">
          · prochaine vers{' '}
          <time dateTime={nextData.toISOString()}>{NEXT_DATA_TIME.format(nextData)}</time>
        </span>
      )}
    </span>
  );
}
