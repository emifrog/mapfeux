/**
 * Sélection des frames radar servables — logique pure, testée seule.
 *
 * Référence : cahier v2.1 §16.6 et §19.3.
 *
 * L'alias est réécrit à chaque passe d'import, mais l'horloge tourne entre
 * deux passes : une frame peut expirer **après** la dernière écriture de
 * l'alias — constaté en production le 26 août, l'alias de 08 h 06 listait
 * encore la frame de 06 h 15, expirée à 08 h 15. La sélection filtre donc
 * par `expire_a` contre l'horloge du lecteur : l'animation ne sert jamais
 * une frame expirée (§16.6), quoi que l'alias liste.
 */

export interface RadarAliasFrame {
  acquise_a: string;
  objet: string;
  expire_a: string;
}

export interface SelectedFrame {
  acquiredAt: Date;
  expiresAt: Date;
  objet: string;
}

/** Les frames encore servables, en ordre chronologique. */
export function selectFrames(entries: RadarAliasFrame[], now: Date): SelectedFrame[] {
  return entries
    .map((entry) => ({
      acquiredAt: new Date(entry.acquise_a),
      expiresAt: new Date(entry.expire_a),
      objet: entry.objet,
    }))
    .filter((frame) => frame.expiresAt.getTime() > now.getTime())
    .sort((a, b) => a.acquiredAt.getTime() - b.acquiredAt.getTime());
}

/** Coins d'une source image MapLibre : UL, UR, BR, BL en (lon, lat). */
export type ImageCoordinates = [
  [number, number],
  [number, number],
  [number, number],
  [number, number],
];

/** L'emprise ouest/sud/est/nord vers les quatre coins de l'image. */
export function extentToCoordinates(extent: [number, number, number, number]): ImageCoordinates {
  const [west, south, east, north] = extent;
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}
