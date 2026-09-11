/**
 * Cadrage d'ouverture de la carte — logique pure, testée seule.
 *
 * Référence : cahier §7.1 et §21.3.
 *
 * ## Pourquoi le centre ne peut pas être une constante
 *
 * `/carte` s'ouvrait au centre géométrique de l'emprise pilote. Le
 * 11 septembre 2026, les neuf événements de la fenêtre courante étaient
 * tous groupés à son bord **ouest** — le plus occidental tombait même
 * hors de l'écran. Une page intitulée « anomalies thermiques observées »
 * s'ouvrait donc sur une carte où l'on n'en voyait aucune, pendant que sa
 * propre liste en annonçait neuf.
 *
 * Le centre suit donc ce qu'il y a à montrer : le milieu de l'étendue des
 * événements servis. Le zoom, lui, ne bouge pas — ajuster le zoom aux
 * données ferait remonter le lavis départemental dès qu'elles sont
 * dispersées (§21.3), et ce lavis est fait pour céder la place aux
 * marqueurs, pas pour les recouvrir.
 *
 * Sans événement, le centre de l'emprise reprend la main : c'est alors
 * l'emprise qui est le sujet, faute d'autre.
 */

export interface FramingPoint {
  longitude: number;
  latitude: number;
}

/**
 * Milieu de l'étendue des points, ou le repli s'il n'y en a aucun.
 *
 * Le **milieu de l'étendue** et non la moyenne : une grappe de sept
 * détections sur un même site tirerait la moyenne à elle et laisserait
 * l'événement isolé du bout de l'emprise hors de l'écran. Ici les deux
 * extrêmes pèsent autant, ce qui est la question posée — que faut-il
 * embrasser.
 *
 * Les coordonnées non finies sont écartées : une longitude manquante ne
 * doit pas emporter le cadrage vers `NaN`, où la carte n'afficherait plus
 * rien du tout.
 */
export function framingCenter(
  points: readonly FramingPoint[],
  fallback: readonly [number, number],
): [number, number] {
  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;

  for (const point of points) {
    if (!Number.isFinite(point.longitude) || !Number.isFinite(point.latitude)) continue;
    minLon = Math.min(minLon, point.longitude);
    maxLon = Math.max(maxLon, point.longitude);
    minLat = Math.min(minLat, point.latitude);
    maxLat = Math.max(maxLat, point.latitude);
  }

  if (minLon === Infinity) return [fallback[0], fallback[1]];
  return [(minLon + maxLon) / 2, (minLat + maxLat) / 2];
}
