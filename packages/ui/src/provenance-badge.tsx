import type { Provenance } from '@mapfeux/domain';

import { cn } from './cn';
import { PROVENANCE_LABELS } from './labels';

/**
 * Marque visuelle de la nature d'une information.
 *
 * Référence : cahier FR-053 et §8.5. Observations, estimations, informations
 * officielles et corrections doivent rester distinguables sans lecture du
 * texte, et sans reposer uniquement sur la couleur — d'où le pictogramme et le
 * libellé explicite.
 */

const PROVENANCE_STYLES: Record<Provenance, string> = {
  observation: 'border-stone-300 bg-stone-50 text-stone-800',
  algorithmic_inference: 'border-violet-300 bg-violet-50 text-violet-900',
  model_estimate: 'border-indigo-300 bg-indigo-50 text-indigo-900 border-dashed',
  official_information: 'border-teal-400 bg-teal-50 text-teal-900',
  editorial_correction: 'border-amber-400 bg-amber-50 text-amber-900',
  external_report: 'border-sky-300 bg-sky-50 text-sky-900',
};

const PROVENANCE_MARKS: Record<Provenance, string> = {
  observation: '◉',
  algorithmic_inference: '⌁',
  model_estimate: '≈',
  official_information: '✓',
  editorial_correction: '✎',
  external_report: '↗',
};

export interface ProvenanceBadgeProps {
  provenance: Provenance;
  className?: string;
}

export function ProvenanceBadge({ provenance, className }: ProvenanceBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium',
        PROVENANCE_STYLES[provenance],
        className,
      )}
    >
      <span aria-hidden="true">{PROVENANCE_MARKS[provenance]}</span>
      {PROVENANCE_LABELS[provenance]}
    </span>
  );
}
