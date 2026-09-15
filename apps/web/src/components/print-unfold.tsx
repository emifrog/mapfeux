'use client';

import { useEffect } from 'react';

/**
 * À l'impression, les plis s'ouvrent — FR-068.
 *
 * Le tableau des observations de la fiche replie tout au-delà de douze
 * lignes dans un `<details>` natif. Fermé, il ne s'imprime pas : la feuille
 * portait « les 45 observations plus anciennes » et rien dessous, constaté
 * le 15 septembre 2026. La feuille de style ouvre le contenu par
 * `::details-content` là où le navigateur le connaît ; ce composant fait la
 * même chose partout où JavaScript tourne, en posant l'attribut `open` à
 * `beforeprint` et en le retirant à `afterprint` — seulement sur les plis
 * qu'il a ouverts lui-même, un pli que le lecteur avait ouvert reste
 * ouvert.
 *
 * Sans JavaScript et sans `::details-content`, la feuille reste partielle
 * et le dit : l'annonce du pli porte son compte.
 */
export function PrintUnfold() {
  useEffect(() => {
    let opened: HTMLDetailsElement[] = [];

    const before = (): void => {
      opened = [...document.querySelectorAll<HTMLDetailsElement>('details:not([open])')];
      for (const details of opened) details.open = true;
    };
    const after = (): void => {
      for (const details of opened) details.open = false;
      opened = [];
    };

    window.addEventListener('beforeprint', before);
    window.addEventListener('afterprint', after);
    return () => {
      window.removeEventListener('beforeprint', before);
      window.removeEventListener('afterprint', after);
    };
  }, []);

  return null;
}
