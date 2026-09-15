/**
 * Les passages satellitaires d'un événement — logique pure, testée seule.
 *
 * Référence : cahier §5.7, FR-080.
 *
 * Une observation FIRMS est un **pixel** : un même passage d'un satellite
 * au-dessus d'un feu en produit plusieurs, tous à la même minute. Lus un
 * par un, cinquante-sept pixels ne disent rien de l'évolution ; regroupés
 * par passage, ils donnent une suite d'instants — c'est l'unité que la
 * relecture emploie déjà (FR-080), et celle qu'un lecteur comprend :
 * « le satellite est passé sept fois ».
 *
 * ## Ce qui fait un passage
 *
 * Le même satellite, à moins de dix minutes d'écart. Un passage dure des
 * secondes et un satellite ne revient pas avant une centaine de minutes :
 * la fenêtre est large pour absorber les heures d'acquisition arrondies à
 * la minute, étroite pour ne jamais fondre deux passages. Deux satellites
 * qui passent à la même minute restent deux passages — ils ne mesurent pas
 * la même chose.
 *
 * ## La puissance cumulée est un calcul
 *
 * La puissance radiative d'un passage est la **somme** des pixels connus.
 * C'est une agrégation, donc une déduction (FR-053) ; la section qui
 * l'affiche porte cette provenance. Un pixel sans puissance ne compte pas
 * pour zéro, il ne compte pas — et un passage dont aucun pixel n'a de
 * puissance reste un passage, sans puissance : il est montré, pas
 * inventé.
 */

export interface PassDetection {
  acquiredAt: Date;
  satellite: string;
  sensor: string;
  frpMw: number | null;
  dayNight: string | null;
}

export interface SatellitePass {
  /** Première acquisition du passage. */
  at: Date;
  satellite: string;
  sensor: string;
  /** Nombre de pixels du passage. */
  pixels: number;
  /** Somme des puissances connues, ou `null` si aucune ne l'est. */
  frpTotalMw: number | null;
  frpMaxMw: number | null;
  /** Jour ou nuit, à la majorité des pixels ; `null` si aucun ne le dit. */
  dayNight: 'D' | 'N' | null;
}

/** Deux acquisitions d'un même satellite à moins de dix minutes : un passage. */
export const PASS_WINDOW_MS = 10 * 60_000;

/**
 * Regroupe les observations par passage, du plus ancien au plus récent.
 *
 * Les acquisitions à date invalide sont écartées : un `NaN` ne se classe
 * pas et emporterait le tri avec lui.
 */
export function groupByPass(detections: readonly PassDetection[]): SatellitePass[] {
  const sorted = detections
    .filter((detection) => Number.isFinite(detection.acquiredAt.getTime()))
    .slice()
    .sort((a, b) => a.acquiredAt.getTime() - b.acquiredAt.getTime());

  interface Draft {
    pass: SatellitePass;
    day: number;
    night: number;
  }

  const open = new Map<string, Draft>();
  const passes: Draft[] = [];

  for (const detection of sorted) {
    const current = open.get(detection.satellite);
    const time = detection.acquiredAt.getTime();

    let draft: Draft;
    if (current !== undefined && time - current.pass.at.getTime() <= PASS_WINDOW_MS) {
      draft = current;
    } else {
      draft = {
        pass: {
          at: detection.acquiredAt,
          satellite: detection.satellite,
          sensor: detection.sensor,
          pixels: 0,
          frpTotalMw: null,
          frpMaxMw: null,
          dayNight: null,
        },
        day: 0,
        night: 0,
      };
      open.set(detection.satellite, draft);
      passes.push(draft);
    }

    draft.pass.pixels += 1;
    if (detection.frpMw !== null && Number.isFinite(detection.frpMw)) {
      draft.pass.frpTotalMw = (draft.pass.frpTotalMw ?? 0) + detection.frpMw;
      draft.pass.frpMaxMw = Math.max(draft.pass.frpMaxMw ?? -Infinity, detection.frpMw);
    }
    if (detection.dayNight === 'D') draft.day += 1;
    else if (detection.dayNight === 'N') draft.night += 1;
  }

  return passes
    .map(({ pass, day, night }) => ({
      ...pass,
      // Les sommes de flottants traînent des poussières : 12,3 + 4,5 n'est
      // pas 16,8. Une puissance s'affiche au dixième de mégawatt.
      frpTotalMw: pass.frpTotalMw === null ? null : Math.round(pass.frpTotalMw * 10) / 10,
      dayNight: day === 0 && night === 0 ? null : ((day >= night ? 'D' : 'N') as 'D' | 'N'),
    }))
    .sort((a, b) => a.at.getTime() - b.at.getTime());
}
