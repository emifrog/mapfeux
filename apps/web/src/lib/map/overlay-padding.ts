/**
 * Surface de carte mangée par les panneaux posés dessus — calcul pur.
 *
 * Référence : cahier §8.3.
 *
 * ## Pourquoi mesurer plutôt qu'écrire
 *
 * Une première version portait quatre nombres en dur, recopiés des largeurs
 * CSS. Ils se sont trompés deux fois en une soirée du 11 septembre 2026 :
 * d'abord parce que la barre temporelle passe à deux lignes sur un écran
 * étroit, ensuite parce que sa hauteur avait tout simplement grandi — deux
 * marqueurs se retrouvaient dessous. Un nombre écrit à la main décrit une
 * mise en page à un instant ; les panneaux, eux, continuent de vivre.
 *
 * Ce module ne touche ni au DOM ni à MapLibre : il reçoit des rectangles et
 * rend quatre retraits, ce qui le rend vérifiable sans navigateur — le seul
 * endroit où les deux erreurs précédentes auraient été visibles.
 */

/** Un rectangle, dans la forme que rend `getBoundingClientRect`. */
export interface Rect {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface Inset {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/** Le bord contre lequel un panneau est posé. Déclaré, jamais deviné. */
export type OverlaySide = 'top' | 'right' | 'bottom' | 'left';

export interface OverlayPanel {
  side: OverlaySide;
  rect: Rect;
}

/**
 * Gouttière laissée entre un panneau et le bord de la zone utile.
 *
 * Sans elle, un marqueur peut affleurer le bord d'un carton, où il se lit
 * mal sans être franchement caché — le pire des deux.
 */
export const OVERLAY_GUTTER = 12;

function overlaps(host: Rect, panel: Rect): boolean {
  return (
    panel.right > host.left &&
    panel.left < host.right &&
    panel.bottom > host.top &&
    panel.top < host.bottom
  );
}

/**
 * Retraits à donner à la caméra pour que la zone utile soit celle qu'on voit.
 *
 * Un panneau qui **ne recouvre pas** la carte ne compte pas : c'est ce qui
 * arrive sous 640 px, où les panneaux s'empilent dessous. Aucun seuil n'est
 * écrit ici — la géométrie suffit à le dire, et elle ne se désynchronise pas
 * d'un point de rupture CSS.
 *
 * Un panneau replié, donc absent du document, ne se mesure pas et ne compte
 * pas non plus : la carte récupère sa place d'elle-même.
 *
 * Le maximum est retenu par côté : deux panneaux au même bord ne s'ajoutent
 * pas, c'est le plus avancé des deux qui décide.
 */
export function overlayPadding(host: Rect, panels: readonly OverlayPanel[]): Inset {
  const inset: Inset = { top: 0, right: 0, bottom: 0, left: 0 };

  for (const { side, rect } of panels) {
    if (!overlaps(host, rect)) continue;

    const depth =
      side === 'left'
        ? rect.right - host.left
        : side === 'right'
          ? host.right - rect.left
          : side === 'top'
            ? rect.bottom - host.top
            : host.bottom - rect.top;

    inset[side] = Math.max(inset[side], Math.round(depth) + OVERLAY_GUTTER);
  }

  return inset;
}
