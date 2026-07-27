import { dataAgeMs, formatDataAge } from '@mapfeux/domain';

import { cn } from './cn';

/**
 * Affichage conjoint de l'horodatage exact et de l'âge de la donnée.
 *
 * Référence : cahier FR-114, FR-116 et §21.5. L'horodatage brut reste toujours
 * présent : l'âge relatif ne le remplace jamais, car il masquerait le décalage
 * entre l'heure d'acquisition satellitaire et l'heure de consultation.
 */

export interface DataAgeProps {
  /** Date de la donnée elle-même, pas de son import. */
  dataAt: Date;
  /** Instant de référence, injecté pour rester testable et rendu serveur. */
  now: Date;
  /** Fuseau d'affichage du territoire consulté. */
  timeZone?: string;
  className?: string;
}

export function DataAge({ dataAt, now, timeZone = 'Europe/Paris', className }: DataAgeProps) {
  const formatter = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone,
  });

  return (
    <span className={cn('inline-flex items-baseline gap-1.5 text-sm', className)}>
      <time dateTime={dataAt.toISOString()}>{formatter.format(dataAt)}</time>
      <span className="text-stone-500">(il y a {formatDataAge(dataAgeMs(dataAt, now))})</span>
    </span>
  );
}
