import { formatDataRecency } from '@mapfeux/domain';
import { CONFIDENCE_LEVEL_LABELS, EVENT_FRESHNESS_LABELS } from '@mapfeux/ui';

/**
 * La carte au survol d'un marqueur — contenu pur, testé seul.
 *
 * Référence : cahier §8.6, FR-006.
 *
 * Sous la souris, avant tout clic : la commune, depuis quand, combien
 * d'observations, quelle fiabilité. C'est ce que la fiche dit en tête, dans
 * les **mêmes mots** que la liste textuelle — un lecteur qui passe de l'une
 * à l'autre ne doit pas avoir à retraduire.
 *
 * ## L'âge se calcule au survol, pas à la construction de la couche
 *
 * La couche porte un `ageHours` figé à sa construction, suffisant pour la
 * couleur. Une page peut rester ouverte des heures pendant une crise ; la
 * carte au survol lit `lastDetectedAt` et compte depuis **maintenant** —
 * sans quoi elle dirait « il y a 2 h » à une observation vieille de six.
 *
 * ## Du HTML, donc de l'échappement
 *
 * MapLibre veut une chaîne. Le nom de commune vient de la base et non du
 * lecteur, mais un nom porte des apostrophes, des esperluettes, et demain
 * peut-être autre chose : tout ce qui vient des données passe par
 * `escapeHtml`, sans exception, parce que l'exception est l'endroit où ça
 * casse.
 */

export interface HoverCardData {
  publicId: string;
  municipality: string;
  /** ISO 8601. */
  lastDetectedAt: string;
  detectionCount: number;
  confidence: string;
  freshness: string;
}

const TIME = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

export function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/**
 * Le contenu de la carte, prêt pour `Popup.setHTML`.
 *
 * Une donnée inconnue ne fait pas disparaître la carte : un statut hors
 * vocabulaire s'affiche tel quel, une commune absente devient « Événement
 * thermique » comme dans la liste, une date invalide donne « date inconnue »
 * par `formatDataRecency`.
 */
export function hoverCardHtml(data: HoverCardData, now: Date): string {
  const title = data.municipality.trim() === '' ? 'Événement thermique' : data.municipality;
  const freshness =
    (EVENT_FRESHNESS_LABELS as Record<string, string>)[data.freshness] ?? data.freshness;
  const confidence =
    (CONFIDENCE_LEVEL_LABELS as Record<string, string>)[data.confidence]?.toLowerCase() ??
    data.confidence;
  const at = new Date(data.lastDetectedAt);
  const when = Number.isNaN(at.getTime()) ? '' : TIME.format(at);
  const count = data.detectionCount;

  return [
    `<p class="mapfeux-hover__title">${escapeHtml(title)}`,
    `<span class="mapfeux-hover__id">${escapeHtml(data.publicId)}</span></p>`,
    `<p class="mapfeux-hover__line">${escapeHtml(freshness)}`,
    ` · <span class="mono">${count}</span> détection${count > 1 ? 's' : ''}`,
    ` · fiabilité ${escapeHtml(confidence)}</p>`,
    `<p class="mapfeux-hover__when">Dernière observation `,
    when === '' ? '' : `<span class="mono">${escapeHtml(when)}</span> `,
    `(${escapeHtml(formatDataRecency(at, now))})</p>`,
    `<p class="mapfeux-hover__hint">Cliquer pour ouvrir la fiche</p>`,
  ].join('');
}
