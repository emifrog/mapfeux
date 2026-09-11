import { describe, expect, it } from 'vitest';

import { DEFAULT_WINDOW_HOURS, TIME_WINDOWS, windowPhrase, windowSince } from './time-windows';

describe('TIME_WINDOWS', () => {
  it('va du plus serré au plus large, et « tout » reste accessible', () => {
    const hours = TIME_WINDOWS.map((window) => window.hours);
    expect(hours).toEqual([12, 24, 48, 168, null]);
  });

  it("le défaut est la frontière de l'archivage — sept jours (§17.4)", () => {
    // `cycle-de-vie-v1` archive au septième jour sans observation : la
    // fenêtre par défaut montre donc exactement ce que le domaine tient
    // pour courant. Changer l'un sans l'autre ferait mentir la carte.
    expect(DEFAULT_WINDOW_HOURS).toBe(7 * 24);
    expect(TIME_WINDOWS.some((window) => window.hours === DEFAULT_WINDOW_HOURS)).toBe(true);
  });
});

describe('windowSince', () => {
  const now = new Date('2026-09-11T12:00:00Z');

  it('recule de la fenêtre demandée', () => {
    expect(windowSince(24, now)?.toISOString()).toBe('2026-09-10T12:00:00.000Z');
    expect(windowSince(168, now)?.toISOString()).toBe('2026-09-04T12:00:00.000Z');
  });

  it('« tout » ne borne rien', () => {
    expect(windowSince(null, now)).toBeUndefined();
  });
});

describe('windowPhrase', () => {
  it('accorde heures et jours sans faute', () => {
    expect(windowPhrase(12)).toBe('dans les 12 dernières heures');
    expect(windowPhrase(24)).toBe('dans les dernières 24 heures');
    expect(windowPhrase(48)).toBe('dans les 2 derniers jours');
    expect(windowPhrase(168)).toBe('dans les 7 derniers jours');
  });

  it("« tout » parle d'emprise, pas de durée", () => {
    expect(windowPhrase(null)).toBe('dans cette emprise');
  });

  it('chaque fenêtre proposée a une formulation', () => {
    for (const window of TIME_WINDOWS) {
      expect(windowPhrase(window.hours)).not.toBe('');
    }
  });
});
