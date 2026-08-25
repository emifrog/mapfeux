/**
 * Échantillonnage ponctuel des rasters de qualité de l'air — logique pure.
 *
 * Référence : cahier v2.1 §19.2 et FR-121.
 *
 * Ce module ne touche ni le réseau ni le DOM : le choix de l'échéance et la
 * conversion position → cellule se testent ici, la lecture du COG vit dans
 * `lib/data/air.ts`. La méthode est le **plus proche voisin** : sur une
 * grille de 0,1°, interpoler une concentration modélisée fabriquerait une
 * précision que la donnée n'a pas.
 */

export interface AirAssetChoice {
  validAt: Date;
}

/**
 * L'actif dont l'heure de validité est la plus proche de l'instant demandé.
 *
 * Le run couvre 24 échéances horaires à partir de 00 UTC : « le plus
 * proche » revient à l'heure courante pendant la journée couverte, et à la
 * dernière échéance quand le run date — c'est alors `isStale` qui parle.
 */
export function pickClosest<T extends AirAssetChoice>(assets: readonly T[], now: Date): T | null {
  let best: T | null = null;
  let bestGap = Number.POSITIVE_INFINITY;
  for (const asset of assets) {
    const gap = Math.abs(asset.validAt.getTime() - now.getTime());
    if (gap < bestGap) {
      best = asset;
      bestGap = gap;
    }
  }
  return best;
}

/**
 * Au-delà de cet écart, la valeur n'est plus présentée comme actuelle.
 *
 * Avec un cron quotidien en bonne santé, l'écart maximal survient juste
 * avant l'import de 08 h 45 UTC : la dernière échéance du run de la veille
 * date de 00 h, soit près de neuf heures. Douze laisse la marge d'un import
 * en retard sans jamais couvrir un run entier manqué — à vingt-quatre
 * heures d'écart, dire « pas de donnée récente » est la seule phrase vraie.
 */
export const STALE_AFTER_MS = 12 * 60 * 60 * 1000;

export function isStale(validAt: Date, now: Date): boolean {
  return Math.abs(now.getTime() - validAt.getTime()) > STALE_AFTER_MS;
}

/** Géoréférencement d'un raster : origine au coin nord-ouest, pas signés. */
export interface GridGeoreference {
  originX: number;
  originY: number;
  resolutionX: number; // degrés par colonne, positif vers l'est
  resolutionY: number; // degrés par ligne, négatif vers le sud
  width: number;
  height: number;
}

/**
 * La cellule contenant un point, ou null hors de la grille.
 *
 * Jamais de rabattement sur la cellule de bord : un point hors d'emprise
 * recevrait la valeur d'un lieu qui n'est pas le sien, en silence — le même
 * piège que le garde-fou de distance du vent (§16.4).
 */
export function nearestCell(
  grid: GridGeoreference,
  longitude: number,
  latitude: number,
): { column: number; row: number } | null {
  const column = Math.floor((longitude - grid.originX) / grid.resolutionX);
  const row = Math.floor((latitude - grid.originY) / grid.resolutionY);
  if (column < 0 || column >= grid.width || row < 0 || row >= grid.height) {
    return null;
  }
  // Au bord nord, Math.floor(0 / -0,1) rend -0, qu'une égalité stricte
  // distingue de 0 ; l'addition de zéro normalise.
  return { column: column + 0, row: row + 0 };
}
