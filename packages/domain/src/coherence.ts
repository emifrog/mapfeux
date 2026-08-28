import type { OfficialControlStatus } from './vocabulary';

/**
 * Cohérence entre observation satellitaire et statut officiel. FR-145,
 * cahier §17.4 et §17.5.
 *
 * Un statut officiel ne se déduit pas et ne s'écrase pas : quand une
 * anomalie thermique est observée après lui, les deux faits s'affichent
 * côte à côte. Seul « éteint » est en divergence avec une observation
 * postérieure : « circonscrit » et « maîtrisé » annoncent par définition
 * une activité qui continue sous contrôle — signaler une divergence sur
 * ces statuts apprendrait à ignorer l'alerte, la leçon de la vigilance.
 *
 * Le même choix vit côté base dans `fire.flag_official_status_divergences`
 * (l'alerte de cohérence pour revue, §17.4) : deux chemins, une définition
 * à garder alignée.
 */

export const DIVERGENT_OFFICIAL_STATUSES = [
  'extinguished',
] as const satisfies readonly OfficialControlStatus[];

export function hasOfficialStatusDivergence(input: {
  officialControlStatus: OfficialControlStatus | null;
  officialStatusAt: Date | string | null;
  lastDetectedAt: Date | string;
}): boolean {
  if (input.officialControlStatus === null || input.officialStatusAt === null) return false;
  if (!(DIVERGENT_OFFICIAL_STATUSES as readonly string[]).includes(input.officialControlStatus)) {
    return false;
  }
  return new Date(input.lastDetectedAt).getTime() > new Date(input.officialStatusAt).getTime();
}
