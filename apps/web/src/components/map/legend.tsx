import { PALETTE } from '@mapfeux/map-style';
import { CONFIDENCE_LEVEL_NOTICE, EVENT_FRESHNESS_LABELS } from '@mapfeux/ui';

/**
 * Légende de la carte. Cahier FR-006 et §6.5.
 *
 * Chaque entrée porte une pastille **et** un libellé : la légende ne repose
 * jamais uniquement sur la couleur.
 *
 * La taille des marqueurs est expliquée, faute de quoi un gros cercle se lirait
 * comme un gros feu. Elle ne dit rien d'autre que le nombre d'observations
 * satellitaires (FR-049).
 */

const ENTRIES = [
  { key: 'new', color: PALETTE.thermal.new },
  { key: 'recent', color: PALETTE.thermal.recent },
  { key: 'not_recent', color: PALETTE.thermal.notRecent },
  { key: 'archived', color: PALETTE.thermal.archived },
] as const;

export function MapLegend() {
  return (
    <section aria-labelledby="legende" className="text-sm">
      <h2 id="legende" className="font-semibold">
        Légende
      </h2>

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
        {ENTRIES.map((entry) => (
          <li key={entry.key} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="inline-block h-3 w-3 rounded-full border border-stone-600"
              style={{ backgroundColor: entry.color }}
            />
            {EVENT_FRESHNESS_LABELS[entry.key]}
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs text-stone-700">
        La taille d’un marqueur suit le <strong>nombre d’observations satellitaires</strong>, et non
        la surface ou la gravité du phénomène, que MapFeux ne connaît pas. {CONFIDENCE_LEVEL_NOTICE}
      </p>
    </section>
  );
}
