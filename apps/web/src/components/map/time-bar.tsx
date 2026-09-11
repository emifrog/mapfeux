'use client';

import { PALETTE } from '@mapfeux/map-style';

import { TIME_WINDOWS, windowPhrase } from '@/lib/map/time-windows';

import { AGE_LEGEND_ENTRIES } from './legend';

/**
 * Barre temporelle de la carte. Cahier FR-005, §17.4, §21.3.
 *
 * Elle porte deux choses au contact de la carte : la **fenêtre** montrée et
 * la **clé de lecture** des couleurs. Les deux répondent à la question que
 * le lecteur se pose devant des points colorés — de quand datent-ils ? — et
 * les séparer obligeait à chercher la réponse ailleurs sur la page.
 *
 * La fenêtre est un filtre **annoncé** : le libellé actif est visible, le
 * compte des événements montrés l'accompagne, et « tout » reste à un clic.
 * C'est la différence entre filtrer et masquer (§17.7). Les fenêtres et
 * leur formulation vivent dans `lib/map/time-windows`, que le rendu serveur
 * emploie pour son premier lot.
 */

export function TimeBar({
  windowHours,
  onWindowHours,
  eventCount,
}: {
  windowHours: number | null;
  onWindowHours: (hours: number | null) => void;
  eventCount: number;
}) {
  return (
    <section
      aria-labelledby="fenetre-temporelle"
      // L'attribution IGN est obligatoire et permanente (§9.5) : la barre
      // s'arrête au-dessus d'elle plutôt que de la recouvrir.
      className="mono rounded-xl border p-3 text-[11px] shadow-lg max-sm:mt-3 sm:absolute sm:bottom-7 sm:left-3 sm:right-3 sm:z-10"
      style={{
        background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
        borderColor: 'var(--border)',
        color: 'var(--text-2)',
        backdropFilter: 'blur(6px)',
      }}
    >
      <h2 id="fenetre-temporelle" className="sr-only">
        Fenêtre affichée et âge des détections
      </h2>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <fieldset>
          <legend className="sr-only">Fenêtre temporelle affichée</legend>
          <div className="flex flex-wrap items-center gap-1">
            <span
              aria-hidden="true"
              className="mr-1 text-[9.5px] uppercase tracking-[0.08em]"
              style={{ color: 'var(--text-3)' }}
            >
              Fenêtre
            </span>
            {TIME_WINDOWS.map((window) => (
              <label
                key={window.label}
                className="cursor-pointer rounded-md border px-2 py-[3px]"
                style={{
                  borderColor:
                    window.hours === windowHours ? 'var(--border-strong)' : 'var(--border)',
                  background: window.hours === windowHours ? 'var(--surface-muted)' : 'transparent',
                  color: window.hours === windowHours ? 'var(--text)' : 'var(--text-2)',
                }}
              >
                <input
                  type="radio"
                  name="fenetre-carte"
                  className="sr-only"
                  checked={window.hours === windowHours}
                  onChange={() => onWindowHours(window.hours)}
                />
                {window.label}
              </label>
            ))}
          </div>
        </fieldset>

        {/* Le compte de ce qui est montré : un filtre qui ne dit pas ce
            qu'il retient se confond avec une absence de phénomène. */}
        <p className="tabular-nums" aria-live="polite">
          <span style={{ color: 'var(--text)' }}>{eventCount}</span> événement
          {eventCount > 1 ? 's' : ''} {windowPhrase(windowHours)}
        </p>

        {/* La clé de lecture : pastille **et** libellé, jamais la couleur
            seule (§6.5). La version complète reste sous la carte. */}
        <ul className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1">
          {AGE_LEGEND_ENTRIES.map((entry) => (
            <li key={entry.label} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="block size-2 shrink-0 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              {entry.label}
            </li>
          ))}
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="block size-2 shrink-0 rounded-full border-[1.4px]"
              style={{ borderColor: PALETTE.thermal.recent }}
            />
            observation isolée
          </li>
        </ul>
      </div>
    </section>
  );
}
