import { dataAgeMs, formatDataAge } from '@mapfeux/domain';
import Link from 'next/link';

import type { DepartmentRow } from '@/lib/map/national-scope';

/**
 * La liste des départements concernés — ce que la colonne de lecture porte
 * à l'échelle nationale.
 *
 * Référence : cahier §8.6, §21.3, FR-003, FR-015.
 *
 * Sous le zoom 7, la carte ne charge aucun événement : le lavis porte les
 * comptes, et cette liste les dit en texte, du plus au moins touché. Elle
 * emprunte les mots de la liste d'événements — étayés, dernière
 * observation, « il y a » — pour qu'un lecteur qui zoome ne change pas de
 * vocabulaire.
 *
 * Choisir un département mène la carte sur lui. Un département ouvert —
 * pilote ou actif — a en plus sa page (FR-015), et le lien y mène sans
 * JavaScript ; les autres n'en ont pas, et on ne leur en promet pas.
 */
export function DepartmentList({
  rows,
  now,
  onFocus,
}: {
  rows: DepartmentRow[];
  now: Date;
  /** Mener la carte sur le département. Absent : rendu serveur, sans carte à mener. */
  onFocus?: (row: DepartmentRow) => void;
}) {
  const touched = rows.filter((row) => row.events > 0);

  if (touched.length === 0) {
    return (
      <p className="text-(--text-2) max-w-[68ch]">
        Aucun événement sur la période consultée. Cela signifie qu’aucune détection thermique n’a
        été regroupée, pas qu’il ne se passe rien.
      </p>
    );
  }

  return (
    <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
      {touched.map((row) => (
        <li key={row.code} className="flex items-baseline gap-3 py-2.5">
          <span className="mono text-small text-(--text-3) w-7 shrink-0">{row.code}</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
              {onFocus !== undefined ? (
                <button
                  type="button"
                  onClick={() => onFocus(row)}
                  className="text-left font-semibold underline-offset-4 hover:underline"
                >
                  {row.name}
                </button>
              ) : (
                <span className="font-semibold">{row.name}</span>
              )}
              {row.hasPage && (
                <Link
                  href={`/territoires/${row.slug}`}
                  className="text-small text-(--text-2) underline underline-offset-4"
                >
                  page du territoire
                </Link>
              )}
            </div>
            <p className="text-small text-(--text-2) mt-0.5">
              <span className="mono">{row.events}</span> événement{row.events > 1 ? 's' : ''}
              <span aria-hidden="true" className="text-(--border-strong) mx-2">
                ·
              </span>
              {row.substantiated === 0 ? (
                'aucun étayé'
              ) : (
                <>
                  <span className="mono">{row.substantiated}</span> étayé
                  {row.substantiated > 1 ? 's' : ''}
                </>
              )}
              <span aria-hidden="true" className="text-(--border-strong) mx-2">
                ·
              </span>
              dernière observation il y a {formatDataAge(dataAgeMs(row.lastDetectedAt, now))}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
