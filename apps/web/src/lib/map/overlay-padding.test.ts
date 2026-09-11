import { describe, expect, it } from 'vitest';

import { overlayPadding, OVERLAY_GUTTER, type OverlayPanel, type Rect } from './overlay-padding';

/** La carte du 12 septembre 2026 en 1024 de large : 1024 × 513, sous la coque. */
const CARTE: Rect = { top: 172, right: 1024, bottom: 685, left: 0 };

/** Colonne de lecture, panneau de calques et barre temporelle, tels que mesurés. */
const COLONNE: OverlayPanel = {
  side: 'left',
  rect: { top: 184, right: 348, bottom: 549, left: 12 },
};
const CALQUES: OverlayPanel = {
  side: 'right',
  rect: { top: 228, right: 1012, bottom: 486, left: 756 },
};
const BARRE: OverlayPanel = {
  side: 'bottom',
  rect: { top: 561, right: 1012, bottom: 637, left: 12 },
};

describe('overlayPadding', () => {
  it('mesure chaque côté jusqu’au bord intérieur du panneau', () => {
    const inset = overlayPadding(CARTE, [COLONNE, CALQUES, BARRE]);
    expect(inset.left).toBe(348 + OVERLAY_GUTTER);
    expect(inset.right).toBe(1024 - 756 + OVERLAY_GUTTER);
    expect(inset.bottom).toBe(685 - 561 + OVERLAY_GUTTER);
    expect(inset.top).toBe(0);
  });

  it('couvre la barre temporelle, que la version écrite à la main ratait', () => {
    // Le nombre en dur valait 100 ; la barre commence 124 px au-dessus du
    // bas de la carte. Deux marqueurs passaient dessous.
    expect(overlayPadding(CARTE, [BARRE]).bottom).toBeGreaterThan(100);
  });

  it('ignore un panneau qui ne recouvre pas la carte', () => {
    // Sous 640 px, les panneaux s'empilent **sous** la carte. Aucun seuil
    // n'est écrit ici : la géométrie suffit à le dire.
    const empile: OverlayPanel = {
      side: 'bottom',
      rect: { top: 700, right: 1012, bottom: 780, left: 12 },
    };
    expect(overlayPadding(CARTE, [empile])).toEqual({ top: 0, right: 0, bottom: 0, left: 0 });
  });

  it('un panneau replié, donc absent, ne prend pas de place', () => {
    const inset = overlayPadding(CARTE, [CALQUES, BARRE]);
    expect(inset.left).toBe(0);
  });

  it('deux panneaux d’un même côté ne s’additionnent pas', () => {
    const secondaire: OverlayPanel = {
      side: 'left',
      rect: { top: 560, right: 200, bottom: 600, left: 12 },
    };
    expect(overlayPadding(CARTE, [COLONNE, secondaire]).left).toBe(348 + OVERLAY_GUTTER);
  });

  it('sans panneau, la carte entière est utile', () => {
    expect(overlayPadding(CARTE, [])).toEqual({ top: 0, right: 0, bottom: 0, left: 0 });
  });
});
