import { describe, expect, it } from 'vitest';

import { bboxSchema, inseeCodeSchema } from './common';

describe('bboxSchema', () => {
  it('accepte une emprise départementale valide', () => {
    const result = bboxSchema.safeParse('6.6,43.4,7.8,44.4');
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.minLon).toBeCloseTo(6.6);
      expect(result.data.maxLat).toBeCloseTo(44.4);
    }
  });

  it('rejette une emprise inversée', () => {
    const result = bboxSchema.safeParse('7.8,44.4,6.6,43.4');
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe('INVALID_BBOX');
    }
  });

  it('rejette une emprise hors bornes géographiques', () => {
    expect(bboxSchema.safeParse('-200,43,7,44').success).toBe(false);
  });

  it('rejette une emprise trop large', () => {
    const result = bboxSchema.safeParse('-10,35,20,55');
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe('BBOX_TOO_LARGE');
    }
  });

  it('rejette une valeur non numérique', () => {
    expect(bboxSchema.safeParse('a,b,c,d').success).toBe(false);
  });
});

describe('inseeCodeSchema', () => {
  it('accepte un code métropolitain', () => {
    expect(inseeCodeSchema.safeParse('06088').success).toBe(true);
  });

  it('accepte les codes corses 2A et 2B', () => {
    expect(inseeCodeSchema.safeParse('2A004').success).toBe(true);
    expect(inseeCodeSchema.safeParse('2B033').success).toBe(true);
  });

  it('rejette un code trop court', () => {
    expect(inseeCodeSchema.safeParse('608').success).toBe(false);
  });
});
