import { describe, expect, it } from 'vitest';

import { isInService, SOURCE_FRESHNESS, type SourceFreshness } from './vocabulary';

/**
 * Décompte des sources affiché au public — cahier FR-150 et §8.1.
 *
 * Le registre déclare six sources ; deux n'ont jamais été construites. Les
 * compter donnait « 1 source sur 6 » sur toutes les pages, soit un service qui
 * s'annonce cassé à 83 % alors qu'il est inachevé. Une source qui n'existe pas
 * encore n'est pas une source en panne.
 */

describe('isInService', () => {
  it('exclut ce qui n’est pas encore construit', () => {
    expect(isInService('upcoming')).toBe(false);
  });

  it('exclut ce qui est volontairement arrêté', () => {
    expect(isInService('maintenance')).toBe(false);
  });

  it('compte une source en panne', () => {
    // `unavailable` est une source en service qui n'a jamais rien livré : c'est
    // exactement ce que le compteur doit montrer.
    expect(isInService('unavailable')).toBe(true);
  });

  it('compte les sources qui livrent, à jour ou en retard', () => {
    expect(isInService('fresh')).toBe(true);
    expect(isInService('delayed')).toBe(true);
    expect(isInService('stale')).toBe(true);
  });

  it('se prononce sur chaque valeur du vocabulaire', () => {
    // Ajouter un état sans décider s'il est « en service » laisserait le
    // compteur trancher par défaut, en silence.
    for (const freshness of SOURCE_FRESHNESS) {
      expect(typeof isInService(freshness)).toBe('boolean');
    }
  });
});

describe('décompte affiché', () => {
  const compter = (sources: SourceFreshness[]) => {
    const enService = sources.filter(isInService);
    return { total: enService.length, sains: enService.filter((f) => f === 'fresh').length };
  };

  it('sort les sources à venir des deux termes du rapport', () => {
    // Les laisser au seul dénominateur creuserait le ratio sans qu'aucune
    // panne existe — l'erreur inverse, et tout aussi trompeuse.
    expect(compter(['fresh', 'fresh', 'upcoming', 'upcoming'])).toEqual({ total: 2, sains: 2 });
  });

  it('reflète l’état réel du service au 5 août 2026', () => {
    // firms trop ancienne, vigilance trop ancienne, arome sans import, ign à
    // jour, cams et radar à venir. Le public lisait « 1 sur 6 » ; il lira
    // « 1/4 » — même panne, sans exagération.
    const reel: SourceFreshness[] = [
      'stale',
      'stale',
      'unavailable',
      'fresh',
      'upcoming',
      'upcoming',
    ];
    expect(compter(reel)).toEqual({ total: 4, sains: 1 });
  });

  it('un registre entièrement à venir ne se présente pas comme sain', () => {
    // `total` à zéro : l'appelant doit traiter ce cas, faute de quoi « 0/0 »
    // passerait pour un service complet.
    expect(compter(['upcoming', 'upcoming'])).toEqual({ total: 0, sains: 0 });
  });
});
