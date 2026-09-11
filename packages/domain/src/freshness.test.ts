import { describe, expect, it } from 'vitest';

import {
  computeEventFreshness,
  computeSourceFreshness,
  dataAgeMs,
  earliestUpcoming,
  formatDataAge,
  HOUR_MS,
  isSnapshotStale,
  MINUTE_MS,
} from './freshness';

const now = new Date('2026-07-27T15:00:00Z');
const hoursAgo = (h: number) => new Date(now.getTime() - h * HOUR_MS);

describe('computeEventFreshness', () => {
  it('classe un événement tout juste créé en « new »', () => {
    expect(
      computeEventFreshness({
        firstDetectedAt: hoursAgo(1),
        lastDetectedAt: hoursAgo(1),
        now,
      }),
    ).toBe('new');
  });

  it('classe une observation du jour en « recent »', () => {
    expect(
      computeEventFreshness({
        firstDetectedAt: hoursAgo(20),
        lastDetectedAt: hoursAgo(6),
        now,
      }),
    ).toBe('recent');
  });

  it('classe une absence d’observation récente en « not_recent » sans conclure', () => {
    expect(
      computeEventFreshness({
        firstDetectedAt: hoursAgo(72),
        lastDetectedAt: hoursAgo(30),
        now,
      }),
    ).toBe('not_recent');
  });

  it('archive au-delà de la fenêtre d’affichage', () => {
    expect(
      computeEventFreshness({
        firstDetectedAt: hoursAgo(400),
        lastDetectedAt: hoursAgo(200),
        now,
      }),
    ).toBe('archived');
  });

  it('donne la priorité au masquage administratif', () => {
    expect(
      computeEventFreshness({
        firstDetectedAt: hoursAgo(1),
        lastDetectedAt: hoursAgo(1),
        now,
        isHidden: true,
      }),
    ).toBe('hidden');
  });
});

describe('computeSourceFreshness', () => {
  const expectedIntervalMs = 10 * MINUTE_MS;
  const staleAfterMs = 3 * HOUR_MS;

  it('retourne « fresh » dans l’intervalle attendu', () => {
    expect(
      computeSourceFreshness({
        lastDataAt: new Date(now.getTime() - 5 * MINUTE_MS),
        now,
        staleAfterMs,
        expectedIntervalMs,
      }),
    ).toBe('fresh');
  });

  it('retourne « delayed » au-delà de l’intervalle attendu', () => {
    expect(
      computeSourceFreshness({
        lastDataAt: new Date(now.getTime() - 40 * MINUTE_MS),
        now,
        staleAfterMs,
        expectedIntervalMs,
      }),
    ).toBe('delayed');
  });

  it('retourne « stale » au-delà du seuil de retard', () => {
    expect(
      computeSourceFreshness({
        lastDataAt: hoursAgo(5),
        now,
        staleAfterMs,
        expectedIntervalMs,
      }),
    ).toBe('stale');
  });

  it('retourne « unavailable » sans donnée connue', () => {
    expect(
      computeSourceFreshness({ lastDataAt: null, now, staleAfterMs, expectedIntervalMs }),
    ).toBe('unavailable');
  });
});

describe('isSnapshotStale', () => {
  it('signale un snapshot ancien sur un événement en cours d’observation', () => {
    expect(
      isSnapshotStale({
        generatedAt: hoursAgo(3),
        now,
        eventFreshness: 'recent',
      }),
    ).toBe(true);
  });

  it('ne signale rien sur un snapshot fraîchement reconstruit', () => {
    expect(
      isSnapshotStale({
        generatedAt: new Date(now.getTime() - 10 * MINUTE_MS),
        now,
        eventFreshness: 'recent',
      }),
    ).toBe(false);
  });

  it('ne signale rien sur un événement sans observation récente', () => {
    // Rien à recalculer : un snapshot ancien y est normal, et le signaler
    // apprendrait à ignorer la bannière.
    expect(
      isSnapshotStale({
        generatedAt: hoursAgo(72),
        now,
        eventFreshness: 'not_recent',
      }),
    ).toBe(false);
    expect(
      isSnapshotStale({
        generatedAt: hoursAgo(72),
        now,
        eventFreshness: 'archived',
      }),
    ).toBe(false);
  });

  it('respecte un seuil personnalisé', () => {
    const generatedAt = new Date(now.getTime() - 20 * MINUTE_MS);
    expect(isSnapshotStale({ generatedAt, now, eventFreshness: 'new' })).toBe(false);
    expect(isSnapshotStale({ generatedAt, now, eventFreshness: 'new', maxAgeMinutes: 15 })).toBe(
      true,
    );
  });
});

describe('dataAgeMs et formatDataAge', () => {
  it('n’autorise jamais un âge négatif', () => {
    expect(dataAgeMs(new Date(now.getTime() + 60_000), now)).toBe(0);
  });

  it('formate les durées en français', () => {
    expect(formatDataAge(30_000)).toBe("moins d'une minute");
    expect(formatDataAge(42 * MINUTE_MS)).toBe('42 min');
    expect(formatDataAge(3 * HOUR_MS)).toBe('3 h');
    expect(formatDataAge(3 * HOUR_MS + 15 * MINUTE_MS)).toBe('3 h 15 min');
    expect(formatDataAge(50 * HOUR_MS)).toBe('2 j 2 h');
  });
});

describe('earliestUpcoming', () => {
  const now = new Date('2026-09-11T15:00:00Z');
  const at = (iso: string) => new Date(iso);

  it("retient l'échéance la plus proche parmi celles à venir", () => {
    const result = earliestUpcoming(
      [at('2026-09-12T00:00:00Z'), at('2026-09-11T19:16:00Z'), at('2026-09-12T02:00:00Z')],
      now,
    );
    expect(result?.toISOString()).toBe('2026-09-11T19:16:00.000Z');
  });

  it('écarte les échéances passées plutôt que de les présenter comme un retard', () => {
    // Le retard se lit sur la pastille et sur /statut : « prochaine il y a
    // deux heures » n'apprendrait rien.
    const result = earliestUpcoming([at('2026-09-11T14:35:00Z'), at('2026-09-11T19:16:00Z')], now);
    expect(result?.toISOString()).toBe('2026-09-11T19:16:00.000Z');
  });

  it('ignore les sources sans échéance', () => {
    expect(earliestUpcoming([null, null], now)).toBeNull();
  });

  it('toutes les échéances passées : rien à annoncer', () => {
    expect(earliestUpcoming([at('2026-09-11T12:00:00Z')], now)).toBeNull();
  });

  it("l'instant présent n'est pas une échéance à venir", () => {
    expect(earliestUpcoming([now], now)).toBeNull();
  });

  it('une date invalide est écartée, pas retenue', () => {
    // `NaN` fait échouer toute comparaison : une date invalide passait donc
    // les filtres et devenait l'échéance. C'est ce qui a fait échouer le
    // build sur une colonne absente de la réponse.
    expect(earliestUpcoming([new Date(undefined as unknown as string)], now)).toBeNull();
    const valide = new Date('2026-09-11T19:16:00Z');
    expect(earliestUpcoming([new Date('pas une date'), valide], now)?.toISOString()).toBe(
      '2026-09-11T19:16:00.000Z',
    );
  });
});
