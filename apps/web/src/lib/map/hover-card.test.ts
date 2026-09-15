import { describe, expect, it } from 'vitest';

import {
  clusterCardHtml,
  escapeHtml,
  hoverCardHtml,
  observationCardHtml,
  type HoverCardData,
  type ObservationCardData,
} from './hover-card';

const NOW = new Date('2026-09-13T20:00:00Z');

const BASE: HoverCardData = {
  publicId: 'MPF-9DVMRWBN',
  municipality: 'Fos-sur-Mer',
  lastDetectedAt: '2026-09-13T15:10:00Z',
  detectionCount: 7,
  confidence: 'medium',
  freshness: 'recent',
};

describe('escapeHtml', () => {
  it('neutralise ce qui ouvrirait une balise ou un attribut', () => {
    expect(escapeHtml(`<b onclick="x">L'Isle & Co</b>`)).toBe(
      '&lt;b onclick=&quot;x&quot;&gt;L&#39;Isle &amp; Co&lt;/b&gt;',
    );
  });
});

describe('hoverCardHtml', () => {
  it('parle comme la liste textuelle : commune, statut, compte, fiabilité, âge', () => {
    const html = hoverCardHtml(BASE, NOW);
    expect(html).toContain('Fos-sur-Mer');
    expect(html).toContain('MPF-9DVMRWBN');
    expect(html).toContain('Observation récente');
    expect(html).toContain('<span class="mono">7</span> détections');
    expect(html).toContain('fiabilité modérée');
    expect(html).toContain('il y a 4 h 50 min');
    expect(html).toContain('Cliquer pour ouvrir la fiche');
  });

  it('compte l’âge depuis maintenant, pas depuis la construction de la couche', () => {
    // Une page ouverte des heures : la même observation doit vieillir.
    const plusTard = new Date('2026-09-14T02:00:00Z');
    expect(hoverCardHtml(BASE, plusTard)).toContain('il y a 10 h 50 min');
  });

  it('accorde le singulier', () => {
    expect(hoverCardHtml({ ...BASE, detectionCount: 1 }, NOW)).toContain(
      '<span class="mono">1</span> détection ·',
    );
  });

  it('échappe le nom de commune, quoi qu’il porte', () => {
    const html = hoverCardHtml({ ...BASE, municipality: "L'Isle-sur-la-Sorgue <b>" }, NOW);
    expect(html).toContain('L&#39;Isle-sur-la-Sorgue &lt;b&gt;');
    expect(html).not.toContain('<b>');
  });

  it('nomme un événement sans commune comme la liste le fait', () => {
    expect(hoverCardHtml({ ...BASE, municipality: '  ' }, NOW)).toContain('Événement thermique');
  });

  it('ne disparaît pas sur un vocabulaire inconnu ou une date invalide', () => {
    const html = hoverCardHtml(
      { ...BASE, freshness: 'inconnu', confidence: 'autre', lastDetectedAt: 'pas une date' },
      NOW,
    );
    expect(html).toContain('inconnu');
    expect(html).toContain('fiabilité autre');
    expect(html).toContain('date inconnue');
  });
});

describe('clusterCardHtml', () => {
  it('dit combien, dont combien d’étayés, et l’âge du plus récent', () => {
    const html = clusterCardHtml({ count: 7, substantiated: 2, minAgeHours: 5.5 });
    expect(html).toContain('<span class="mono">7</span> événements');
    expect(html).toContain('<span class="mono">2</span> étayés');
    expect(html).toContain('5 observations isolées');
    expect(html).toContain('il y a 5 h 30 min');
    expect(html).toContain('Cliquer pour rapprocher');
  });

  it('accorde les singuliers', () => {
    const html = clusterCardHtml({ count: 2, substantiated: 1, minAgeHours: 1 });
    expect(html).toContain('<span class="mono">1</span> étayé ·');
    expect(html).toContain('1 observation isolée');
  });

  it('dit « aucun » plutôt que « 0 »', () => {
    expect(clusterCardHtml({ count: 4, substantiated: 0, minAgeHours: 2 })).toContain(
      'dont aucun étayé',
    );
  });

  it('tait l’âge quand il n’est pas un nombre plutôt que d’en inventer un', () => {
    expect(clusterCardHtml({ count: 3, substantiated: 0, minAgeHours: Number.NaN })).not.toContain(
      'Le plus récent',
    );
  });
});

describe('observationCardHtml', () => {
  const OBSERVATION: ObservationCardData = {
    publicId: 'MPF-VHR8YJ85',
    acquiredAt: '2026-09-13T15:10:00Z',
    sensor: 'VIIRS',
    satellite: 'N20',
    dayNight: 'N',
    frpMw: 12.34,
    confidence: 'medium',
  };

  it('parle comme la ligne du tableau : heure, capteur, confiance, puissance', () => {
    const html = observationCardHtml(OBSERVATION, NOW, { link: false });
    expect(html).toContain('Observation satellitaire');
    expect(html).toContain('N20 · VIIRS');
    expect(html).toContain('il y a 4 h 50 min');
    expect(html).toContain('· nuit');
    expect(html).toContain('confiance modérée');
    expect(html).toContain('<span class="mono">12,3</span> MW');
  });

  it('ne propose de cliquer que s’il y a une fiche à ouvrir', () => {
    expect(observationCardHtml(OBSERVATION, NOW, { link: false })).not.toContain('Cliquer');
    expect(observationCardHtml(OBSERVATION, NOW, { link: true })).toContain(
      'Cliquer pour ouvrir la fiche MPF-VHR8YJ85',
    );
  });

  it('dit une puissance inconnue plutôt que zéro, et une confiance inconnue en clair', () => {
    const html = observationCardHtml(
      { ...OBSERVATION, frpMw: null, confidence: 'unknown', dayNight: null },
      NOW,
      { link: false },
    );
    expect(html).toContain('puissance non disponible');
    expect(html).toContain('confiance inconnue');
    expect(html).not.toContain('· nuit');
    expect(html).not.toContain('· jour');
  });

  it('échappe ce qui vient des données', () => {
    const html = observationCardHtml({ ...OBSERVATION, satellite: '<b>N20</b>' }, NOW, {
      link: false,
    });
    expect(html).toContain('&lt;b&gt;N20&lt;/b&gt;');
    expect(html).not.toContain('<b>');
  });
});
