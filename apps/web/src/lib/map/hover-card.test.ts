import { describe, expect, it } from 'vitest';

import { escapeHtml, hoverCardHtml, type HoverCardData } from './hover-card';

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
