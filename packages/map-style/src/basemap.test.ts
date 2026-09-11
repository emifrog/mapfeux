import { describe, expect, it } from 'vitest';

import {
  buildIgnBasemapStyle,
  IGN_ATTRIBUTION,
  IGN_VECTOR_STYLES,
  ignTileUrl,
  ignVectorStyleUrl,
  withoutRetinaSprite,
} from './basemap';

describe('ignTileUrl', () => {
  it('laisse les gabarits MapLibre non encodés', () => {
    const url = ignTileUrl('plan');
    // Encodés en %7Bz%7D, MapLibre ne les substituerait pas et le fond
    // resterait vide sans erreur visible.
    expect(url).toContain('TILEMATRIX={z}');
    expect(url).toContain('TILEROW={y}');
    expect(url).toContain('TILECOL={x}');
    expect(url).not.toContain('%7B');
  });

  it('cible la couche Plan IGN par défaut', () => {
    expect(ignTileUrl('plan')).toContain('LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2');
  });

  it('utilise le jeu de matrices Web Mercator', () => {
    expect(ignTileUrl('plan')).toContain('TILEMATRIXSET=PM');
  });
});

describe('buildIgnBasemapStyle', () => {
  it('produit un style raster valide pour MapLibre', () => {
    const style = buildIgnBasemapStyle();
    expect(style.version).toBe(8);
    expect(style.sources['ign-basemap'].type).toBe('raster');
    expect(style.layers).toHaveLength(1);
    expect(style.layers[0]?.source).toBe('ign-basemap');
  });

  it("porte l'attribution IGN, obligatoire", () => {
    const style = buildIgnBasemapStyle();
    expect(style.sources['ign-basemap'].attribution).toBe(IGN_ATTRIBUTION);
    expect(IGN_ATTRIBUTION).toContain('IGN');
  });

  it('demande du JPEG pour l’orthophotographie', () => {
    const style = buildIgnBasemapStyle('orthophoto');
    expect(style.sources['ign-basemap'].tiles[0]).toContain('FORMAT=image%2Fjpeg');
  });
});

describe('ignVectorStyleUrl', () => {
  it('sert le style gris par défaut', () => {
    // Le fond doit se retirer devant la donnée : sur un fond en couleurs,
    // l'orange des détections entre en concurrence avec le décor.
    expect(ignVectorStyleUrl()).toBe(IGN_VECTOR_STYLES.gris);
  });

  it('expose le style standard pour se repérer', () => {
    expect(ignVectorStyleUrl('standard')).toContain('standard.json');
  });

  it('ne sert que des URL Géoplateforme en HTTPS', () => {
    for (const url of Object.values(IGN_VECTOR_STYLES)) {
      expect(url).toMatch(/^https:\/\/data\.geopf\.fr\//);
    }
  });
});

describe('withoutRetinaSprite', () => {
  const SPRITE =
    'https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/sprite/PlanIgn-Gris';

  it('retire le suffixe haute densité, que la Géoplateforme ne publie pas', () => {
    // Sondé le 11 septembre 2026 : `.png` et `.json` répondent 200, leurs
    // variantes `@2x` répondent 404. Sans cette réécriture, aucun motif de
    // surface ne se dessine sur un écran moderne.
    expect(withoutRetinaSprite(`${SPRITE}@2x.png`)).toBe(`${SPRITE}.png`);
    expect(withoutRetinaSprite(`${SPRITE}@2x.json`)).toBe(`${SPRITE}.json`);
  });

  it('laisse intacte une URL qui n’en porte pas', () => {
    expect(withoutRetinaSprite(`${SPRITE}.png`)).toBe(`${SPRITE}.png`);
  });

  it('ne touche qu’au nom de fichier', () => {
    expect(withoutRetinaSprite('https://exemple.fr/@2x/sprite.png')).toBe(
      'https://exemple.fr/@2x/sprite.png',
    );
  });
});
