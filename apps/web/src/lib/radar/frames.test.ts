import { describe, expect, it } from 'vitest';

import { extentToCoordinates, selectFrames } from './frames';

describe('selectFrames', () => {
  it("écarte la frame expirée que l'alias liste encore — le cas du 26 août", () => {
    // L'alias écrit à 08 h 06 listait la frame de 06 h 15, expirée à
    // 08 h 15 ; à 08 h 19, elle ne doit plus être servie (§16.6).
    const frames = selectFrames(
      [
        {
          acquise_a: '2026-08-26T06:15:00+00:00',
          objet: 'radar/lame-d-eau/20260826/0615-aaaaaaaaaaaa.png',
          expire_a: '2026-08-26T08:15:00+00:00',
        },
        {
          acquise_a: '2026-08-26T07:20:00+00:00',
          objet: 'radar/lame-d-eau/20260826/0720-bbbbbbbbbbbb.png',
          expire_a: '2026-08-26T09:20:00+00:00',
        },
      ],
      new Date('2026-08-26T08:19:00Z'),
    );
    expect(frames).toHaveLength(1);
    expect(frames[0]?.objet).toContain('0720');
  });

  it('rend les frames en ordre chronologique quel que soit celui du fichier', () => {
    const frames = selectFrames(
      [
        {
          acquise_a: '2026-08-26T08:00:00+00:00',
          objet: 'b.png',
          expire_a: '2026-08-26T10:00:00+00:00',
        },
        {
          acquise_a: '2026-08-26T07:20:00+00:00',
          objet: 'a.png',
          expire_a: '2026-08-26T09:20:00+00:00',
        },
      ],
      new Date('2026-08-26T08:19:00Z'),
    );
    expect(frames.map((frame) => frame.objet)).toEqual(['a.png', 'b.png']);
  });

  it('toutes expirées : liste vide, jamais une vieille pluie', () => {
    const frames = selectFrames(
      [
        {
          acquise_a: '2026-08-26T05:00:00+00:00',
          objet: 'a.png',
          expire_a: '2026-08-26T07:00:00+00:00',
        },
      ],
      new Date('2026-08-26T12:00:00Z'),
    );
    expect(frames).toEqual([]);
  });
});

describe('extentToCoordinates', () => {
  it("l'emprise ouest/sud/est/nord devient UL, UR, BR, BL", () => {
    expect(extentToCoordinates([-9.9, 37.4, 17.6, 54.2])).toEqual([
      [-9.9, 54.2],
      [17.6, 54.2],
      [17.6, 37.4],
      [-9.9, 37.4],
    ]);
  });
});
