import { describe, expect, it } from 'vitest';

import { buildIgnBasemapStyle, IGN_ATTRIBUTION, ignTileUrl } from './basemap';

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
