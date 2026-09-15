import { formatDataAge, formatDataRecency } from '@mapfeux/domain';
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

export interface ObservationCardData {
  /** L'événement dont l'observation est membre. */
  publicId: string;
  /** ISO 8601. */
  acquiredAt: string;
  sensor: string;
  satellite: string;
  /** `'D'`, `'N'` ou rien. */
  dayNight: string | null;
  frpMw: number | null;
  /** Confiance de l'observation elle-même — `'unknown'` compris. */
  confidence: string;
}

const MW = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

/**
 * La carte au survol d'un point de l'**empreinte** : une observation, pas
 * un événement. Elle dit ce que dit la ligne du tableau — heure
 * d'acquisition, capteur, confiance, puissance — dans les mêmes mots, et
 * elle ne propose de cliquer que s'il y a une fiche à ouvrir : sur la
 * fiche elle-même, le clic ne ferait que recharger la page.
 */
export function observationCardHtml(
  data: ObservationCardData,
  now: Date,
  options: { link: boolean },
): string {
  const at = new Date(data.acquiredAt);
  const when = Number.isNaN(at.getTime()) ? '' : TIME.format(at);
  const confidence =
    data.confidence === 'unknown'
      ? 'inconnue'
      : ((CONFIDENCE_LEVEL_LABELS as Record<string, string>)[data.confidence]?.toLowerCase() ??
        data.confidence);
  const period = data.dayNight === 'D' ? ' · jour' : data.dayNight === 'N' ? ' · nuit' : '';
  const power =
    data.frpMw === null || !Number.isFinite(data.frpMw)
      ? 'puissance non disponible'
      : `<span class="mono">${MW.format(data.frpMw)}</span> MW`;

  return [
    `<p class="mapfeux-hover__title">Observation satellitaire`,
    `<span class="mapfeux-hover__id">${escapeHtml(`${data.satellite} · ${data.sensor}`)}</span></p>`,
    `<p class="mapfeux-hover__when">Acquise `,
    when === '' ? '' : `<span class="mono">${escapeHtml(when)}</span> `,
    `(${escapeHtml(formatDataRecency(at, now))})${period}</p>`,
    `<p class="mapfeux-hover__line">confiance ${escapeHtml(confidence)} · ${power}</p>`,
    options.link
      ? `<p class="mapfeux-hover__hint">Cliquer pour ouvrir la fiche ${escapeHtml(data.publicId)}</p>`
      : '',
  ].join('');
}

export interface ClusterCardData {
  count: number;
  substantiated: number;
  /** Âge du membre le plus récent, en heures. */
  minAgeHours: number;
}

/**
 * La carte au survol d'une **grappe** : combien, dont combien d'étayés, et
 * depuis quand pour le plus récent. Pas de commune — une grappe en couvre
 * plusieurs — et le clic ne mène pas à une fiche, il rapproche.
 */
export function clusterCardHtml(data: ClusterCardData): string {
  const count = Math.max(0, Math.round(data.count));
  const substantiated = Math.max(0, Math.round(data.substantiated));
  const age = Number.isFinite(data.minAgeHours)
    ? formatDataAge(Math.max(0, data.minAgeHours) * 3_600_000)
    : null;

  return [
    `<p class="mapfeux-hover__title"><span class="mono">${count}</span> événements</p>`,
    // « dont aucun étayé » et non « dont 0 étayé » : un zéro se lit, il ne se dit pas.
    substantiated === 0
      ? `<p class="mapfeux-hover__line">dont aucun étayé`
      : `<p class="mapfeux-hover__line">dont <span class="mono">${substantiated}</span> étayé${substantiated > 1 ? 's' : ''}`,
    ` · ${count - substantiated} observation${count - substantiated > 1 ? 's' : ''} isolée${count - substantiated > 1 ? 's' : ''}</p>`,
    age === null
      ? ''
      : `<p class="mapfeux-hover__when">Le plus récent : il y a ${escapeHtml(age)}</p>`,
    `<p class="mapfeux-hover__hint">Cliquer pour rapprocher</p>`,
  ].join('');
}
