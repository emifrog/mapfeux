'use client';

import { ignVectorStyleUrl, toDarkVectorStyle } from '@mapfeux/map-style';
import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';

import { effectiveTheme } from '@/components/theme-toggle';

/**
 * Fond de carte, dans le thème courant.
 *
 * Référence : cahier §6.5 et §8.1.
 *
 * La Géoplateforme ne publie pas de feuille sombre ; celle-ci est dérivée
 * de la feuille « gris » par `toDarkVectorStyle`. Ce module est le point
 * de contact entre cette transformation pure et MapLibre.
 *
 * ## Pourquoi `transformStyle` et non une feuille déjà construite
 *
 * Charger la feuille nous-mêmes pour remettre un objet à MapLibre semble
 * plus direct. C'est en fait le chemin le plus lent : `Style.loadJSON`
 * attend une **image d'animation** avant de charger, tandis que
 * `Style.loadURL` charge depuis la réponse réseau (relevé le 11 septembre
 * 2026 dans maplibre-gl 5.24). Un onglet ouvert en arrière-plan ne reçoit
 * pas d'image d'animation : la carte y resterait vide jusqu'à ce qu'on la
 * regarde — et rien, dans les journaux, ne dirait pourquoi.
 *
 * `transformStyle` est le point d'entrée prévu par MapLibre pour retoucher
 * une feuille au moment où elle est chargée. Il garde le chemin `loadURL`,
 * n'ajoute aucune requête, et sert les deux thèmes par le même code.
 */

/** Le thème est sombre — choix explicite, sinon réglage du système. */
export function isDarkTheme(): boolean {
  return effectiveTheme() === 'dark';
}

/**
 * Pose le fond sur la carte, clair ou sombre.
 *
 * `diff: false` est délibéré. La mise à jour différentielle calculerait la
 * suppression de nos calques — ils n'existent pas dans la feuille cible —
 * et `style.load` ne tirerait pas pour les reposer. Un rechargement franc
 * coûte des tuiles, une fois, à chaque bascule de thème.
 */
export function applyBasemapStyle(map: MapLibreMap, dark: boolean): void {
  map.setStyle(ignVectorStyleUrl('gris'), {
    diff: false,
    transformStyle: (_previous, next: StyleSpecification) =>
      dark ? toDarkVectorStyle(next) : next,
  });
}

/**
 * Prévient à chaque changement de thème.
 *
 * Deux sources, parce que le thème en a deux : l'attribut posé sur la
 * racine par la bascule, et la préférence du système tant qu'aucun choix
 * n'a été fait. Manquer la seconde laisserait une carte claire sur une
 * page passée au sombre toute seule, à la tombée du jour.
 */
export function subscribeTheme(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });

  const media = window.matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', onChange);

  return () => {
    observer.disconnect();
    media.removeEventListener('change', onChange);
  };
}
