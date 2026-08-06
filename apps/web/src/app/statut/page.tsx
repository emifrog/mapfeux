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

/**
 * Libellé d'un état, y compris d'un état que ce front ne connaît pas encore.
 *
 * La valeur vient de la vue `api.source_status`, donc de la base — laquelle
 * peut devancer le front d'un déploiement. C'est arrivé le 5 août : la
 * migration introduisant `upcoming` a été appliquée avant la mise en ligne du
 * libellé, et CAMS comme le radar ont affiché une **pastille vide**, sans un
 * mot. Un état muet est pire qu'un état approximatif : le lecteur ne sait même
 * pas qu'il manque quelque chose.
 *
 * Le repli n'invente rien. Traduire l'inconnu en « Indisponible » affirmerait
 * une panne que la page n'a pas constatée, ce que §2.4 proscrit.
 */
function freshnessLabel(freshness: string): string {
  const labels: Record<string, string | undefined> = SOURCE_FRESHNESS_LABELS;
  return labels[freshness] ?? 'État inconnu';
}

function SourceRow({ source, now }: { source: SourceStatusRow; now: Date }) {
  const dataAt = source.last_data_at === null ? null : new Date(source.last_data_at);

  return (
    <tr className="border-b align-top" style={{ borderColor: 'var(--border)' }}>
      <th scope="row" className="py-3.5 pr-4 text-left font-semibold">
        {source.name}
        <span className="eyebrow mt-0.5 block">{source.provider}</span>
      </th>
      <td className="py-3.5 pr-4">
        <span
          className="text-small inline-block rounded-full px-3 py-1 font-medium"
          style={FRESHNESS_STYLES[source.freshness] ?? FRESHNESS_STYLES['unavailable']}
        >
          {freshnessLabel(source.freshness)}
        </span>
      </td>
      <td className="text-small py-3.5 pr-4">
        {dataAt === null ? (
          <span className="text-(--text-3)">Aucune donnée</span>
        ) : (
          <>
            {/* L'horodatage est une mesure : chasse fixe et chiffres tabulaires,
                pour qu'une colonne de dates se lise en colonne. */}
            <time dateTime={dataAt.toISOString()} className="mono">
              {new Intl.DateTimeFormat('fr-FR', {
                dateStyle: 'short',
                timeStyle: 'short',
                timeZone: 'Europe/Paris',
              }).format(dataAt)}
            </time>
            <span className="text-micro text-(--text-3) mt-0.5 block">
              il y a {formatDataAge(Math.max(0, now.getTime() - dataAt.getTime()))}
            </span>
          </>
        )}
      </td>
      <td className="text-small py-3.5">
        {source.incident_message === null ? (
          <span className="text-(--text-3)">—</span>
        ) : (
          <span className="text-degraded">{source.incident_message}</span>
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
    <div className="shell max-w-[880px] py-10">
      <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-2">
        <span>état des données</span>
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>{sources.length} sources déclarées</span>
      </nav>

      <h1 className="text-display mt-3 max-w-[15ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        État des données
      </h1>

      <p className="text-lead text-(--text-2) mt-4 max-w-[68ch]">
        Chaque source est indépendante. L’indisponibilité de l’une n’empêche pas l’affichage des
        autres : les couches concernées sont signalées comme indisponibles plutôt que masquées
        silencieusement.
      </p>

      {!result.readable ? (
        // La page doit rester lisible quand sa propre source de vérité tombe.
        // Annoncer l'ignorance vaut mieux qu'un tableau vide, qui se lirait
        // comme « aucune source en panne ».
        <p
          className="text-small mt-8 rounded-md border-l-[3px] px-4 py-3"
          style={{
            background: 'var(--color-degraded-wash)',
            borderColor: 'var(--color-degraded)',
            color: 'var(--color-degraded)',
          }}
        >
          L’état des sources n’est pas consultable actuellement. Cette page ne reflète donc pas la
          situation réelle des imports.
        </p>
      ) : sources.length === 0 ? (
        <p
          className="text-small mt-8 rounded-md border p-4"
          style={{ background: 'var(--surface-muted)', borderColor: 'var(--border)' }}
        >
          Aucune source de données n’est encore enregistrée sur cette instance.
        </p>
      ) : (
        <div className="mt-10 overflow-x-auto">
          <table className="min-w-xl w-full border-collapse text-left">
            <caption className="sr-only">
              Fraîcheur des sources de données, dernière donnée disponible et incidents en cours
            </caption>
            <thead>
              <tr className="eyebrow border-b-2" style={{ borderColor: 'var(--border-strong)' }}>
                <th scope="col" className="py-2.5 pr-4">
                  Source
                </th>
                <th scope="col" className="py-2.5 pr-4">
                  État
                </th>
                <th scope="col" className="py-2.5 pr-4">
                  Dernière donnée
                </th>
                <th scope="col" className="py-2.5">
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

      {/* Trois horodatages coexistent sur ce site et ne se confondent jamais :
          l'heure de service de la page, celle de la donnée, celle de l'import.
          Celui-ci est le premier, et il le dit. */}
      <p className="text-micro text-(--text-3) mt-10">
        Page générée le{' '}
        <time dateTime={now.toISOString()} className="mono">
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
