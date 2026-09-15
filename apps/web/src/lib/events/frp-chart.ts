import type { SatellitePass } from './passes';

/**
 * Le graphique de puissance radiative par passage — géométrie pure.
 *
 * Référence : cahier §5.7, §6.5.
 *
 * Le composant ne fait que poser des rectangles : tout ce qui se calcule
 * est ici, et se teste sans navigateur. Les coordonnées sont exprimées dans
 * une **boîte de mille sur cent** que le SVG étire à la largeur de la page
 * (`preserveAspectRatio="none"`) — un graphique sert la colonne qu'on lui
 * donne, sur un téléphone comme sur un écran large, et ses libellés
 * restent en HTML à côté, pour ne pas rétrécir avec lui.
 *
 * ## Ce que le graphique affirme, et ce qu'il tait
 *
 * L'échelle part de zéro : une barre deux fois plus haute dit une puissance
 * deux fois plus grande, et rien d'autre. Un passage sans puissance connue
 * n'est pas omis — il serait lu comme un passage sans feu — mais marqué au
 * sol, sans hauteur. Moins de deux passages à puissance connue : pas de
 * graphique, une barre seule ne montre aucune évolution.
 */

export const CHART_WIDTH = 1000;
export const CHART_HEIGHT = 100;

/** Une barre ne dépasse jamais ce tiers de l'espace entre deux passages. */
const BAR_FILL_RATIO = 0.6;
const BAR_MAX_WIDTH = 24;
const BAR_MIN_WIDTH = 4;

export interface ChartBar {
  pass: SatellitePass;
  /** Bord gauche, dans la boîte. */
  x: number;
  width: number;
  /** Bord haut ; `CHART_HEIGHT` pour une barre sans hauteur. */
  y: number;
  height: number;
  /** Puissance connue, donc barre pleine — sinon simple marque au sol. */
  known: boolean;
}

export interface ChartTick {
  value: number;
  /** Position verticale, dans la boîte. */
  y: number;
}

export interface FrpChartModel {
  bars: ChartBar[];
  /** Graduations horizontales, de bas en haut : zéro, milieu, plafond. */
  yTicks: ChartTick[];
  /** Plafond de l'échelle, en mégawatts — un nombre rond au-dessus du maximum. */
  maxMw: number;
  /** Premier et dernier passage : les deux bornes de l'axe du temps. */
  span: { from: Date; to: Date };
}

/**
 * Un plafond rond au-dessus d'une valeur : 1, 2 ou 5 fois une puissance de
 * dix. Une échelle qui s'arrête pile sur le maximum colle la barre au bord,
 * et un plafond quelconque — 137 — ne se lit pas.
 */
export function niceCeiling(value: number): number {
  if (!(value > 0)) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const factor of [1, 2, 5, 10]) {
    if (factor * magnitude >= value) return factor * magnitude;
  }
  return 10 * magnitude;
}

export function frpChartModel(passes: readonly SatellitePass[]): FrpChartModel | null {
  const known = passes.filter((pass) => pass.frpTotalMw !== null);
  if (known.length < 2) return null;

  const maxMw = niceCeiling(Math.max(...known.map((pass) => pass.frpTotalMw ?? 0)));
  const times = passes.map((pass) => pass.at.getTime());
  const from = Math.min(...times);
  const to = Math.max(...times);

  // L'espace entre deux passages, en unités de boîte, borne la largeur des
  // barres : elles ne se recouvrent pas. Passages serrés, barres fines —
  // jamais sous quatre unités, où une barre ne se voit plus.
  const spacing = passes.length > 1 ? CHART_WIDTH / (passes.length - 1) : CHART_WIDTH;
  const width = Math.max(BAR_MIN_WIDTH, Math.min(BAR_MAX_WIDTH, spacing * BAR_FILL_RATIO));

  // Les barres extrêmes tiennent entières dans la boîte : l'axe du temps
  // court de la moitié d'une barre à la moitié d'une barre du bord.
  const left = width / 2;
  const usable = CHART_WIDTH - width;
  const scaleX = (time: number): number =>
    to === from ? CHART_WIDTH / 2 : left + ((time - from) / (to - from)) * usable;

  const bars: ChartBar[] = passes.map((pass) => {
    const x = scaleX(pass.at.getTime()) - width / 2;
    if (pass.frpTotalMw === null) {
      return { pass, x, width, y: CHART_HEIGHT, height: 0, known: false };
    }
    const height = (pass.frpTotalMw / maxMw) * CHART_HEIGHT;
    return { pass, x, width, y: CHART_HEIGHT - height, height, known: true };
  });

  return {
    bars,
    yTicks: [
      { value: 0, y: CHART_HEIGHT },
      { value: maxMw / 2, y: CHART_HEIGHT / 2 },
      { value: maxMw, y: 0 },
    ],
    maxMw,
    span: { from: new Date(from), to: new Date(to) },
  };
}
