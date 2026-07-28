import { PALETTE } from '@mapfeux/map-style';

/**
 * Légende de la carte. Cahier FR-006 et §6.5.
 *
 * Elle porte sur l'**âge de l'observation**, pas sur le statut de l'événement.
 * Les deux répondent à des questions différentes, et c'est l'âge qui se lit
 * d'un coup d'œil sur une carte.
 *
 * Chaque entrée a une pastille **et** un libellé : jamais la couleur seule.
 */

const ENTRIES = [
  { color: PALETTE.thermal.new, label: 'moins de 3 h' },
  { color: PALETTE.thermal.recent, label: '3 à 12 h' },
  { color: PALETTE.thermal.notRecent, label: '12 à 24 h' },
  { color: PALETTE.thermal.archived, label: 'plus de 24 h' },
] as const;

export function MapLegend() {
  return (
    <section
      aria-labelledby="legende"
      className="mono rounded-xl border p-3 text-[11px]"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border)',
        color: 'var(--text-2)',
      }}
    >
      <h2
        id="legende"
        className="mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
        style={{ color: 'var(--text)' }}
      >
        Âge de la détection
      </h2>

      <ul className="flex flex-wrap gap-x-5 gap-y-1.5">
        {ENTRIES.map((entry) => (
          <li key={entry.label} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="block size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            {entry.label}
          </li>
        ))}
        <li className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="block size-2.5 shrink-0 rounded-full border-[1.5px] border-dashed"
            style={{ borderColor: PALETTE.neutral.muted }}
          />
          source connue
        </li>
        <li className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="rounded-xs block size-2.5 shrink-0"
            style={{ backgroundColor: PALETTE.official }}
          />
          information officielle
        </li>
      </ul>

      <p className="mt-3 font-sans text-xs leading-relaxed" style={{ color: 'var(--text-2)' }}>
        La taille d’un marqueur suit le <strong>nombre d’observations</strong> satellitaires, et non
        la surface ou la gravité du phénomène, que MapFeux ne connaît pas.
      </p>
    </section>
  );
}
