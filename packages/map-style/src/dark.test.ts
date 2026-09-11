import { describe, expect, it } from 'vitest';

import {
  DARK_CEILING,
  DARK_FLOOR,
  darkenColor,
  formatColor,
  MAX_SATURATION,
  parseColor,
  PATTERN_OPACITY,
  rgbToHsl,
  toDarkVectorStyle,
} from './dark';

describe('parseColor', () => {
  it('lit les formes que la feuille IGN emploie', () => {
    // Relevé sur `gris.json` le 11 septembre 2026 : 525 couleurs
    // hexadécimales et 107 `rgba()`, rien d'autre.
    expect(parseColor('#FFFFFF')).toEqual({ r: 255, g: 255, b: 255, a: 1 });
    expect(parseColor('#CDCDCD')).toEqual({ r: 205, g: 205, b: 205, a: 1 });
    expect(parseColor('rgba(255, 255, 255, 0.5)')).toEqual({ r: 255, g: 255, b: 255, a: 0.5 });
  });

  it('lit aussi les formes courtes, hsl et les alphas hexadécimaux', () => {
    expect(parseColor('#fff')).toEqual({ r: 255, g: 255, b: 255, a: 1 });
    expect(parseColor('#00000080')?.a).toBeCloseTo(0.502, 2);
    const bleu = parseColor('hsl(210, 100%, 50%)');
    expect(bleu?.b).toBeCloseTo(255, 0);
    expect(bleu?.r).toBeCloseTo(0, 0);
  });

  it('rend null sur ce qui n’est pas une couleur', () => {
    // Les propriétés de couleur contiennent des expressions : les noms
    // d'opérateurs y voisinent avec les couleurs et ne doivent pas être
    // pris pour telles.
    for (const mot of ['interpolate', 'linear', 'zoom', 'case', 'white', '']) {
      expect(parseColor(mot)).toBeNull();
    }
  });
});

describe('formatColor', () => {
  it('rend de l’hexadécimal quand la couleur est opaque, du rgba sinon', () => {
    expect(formatColor({ r: 18, g: 18, b: 18, a: 1 })).toBe('#121212');
    expect(formatColor({ r: 18, g: 18, b: 18, a: 0.5 })).toBe('rgba(18, 18, 18, 0.5)');
  });

  it('fait un aller-retour sans perte sur les gris de la feuille', () => {
    for (const couleur of ['#FFFFFF', '#F2F2F2', '#CDCDCD', '#949494', '#505050', '#000000']) {
      const lu = parseColor(couleur);
      expect(lu).not.toBeNull();
      expect(formatColor(lu as NonNullable<typeof lu>).toUpperCase()).toBe(couleur);
    }
  });
});

describe('darkenColor', () => {
  it('borne les extrêmes : ni noir absolu, ni blanc absolu', () => {
    // Un fond parfaitement noir ferait des marqueurs orange des trous de
    // lumière ; un texte parfaitement blanc leur disputerait l'attention.
    const fond = parseColor(darkenColor('#FFFFFF'));
    const texte = parseColor(darkenColor('#000000'));
    expect(rgbToHsl(fond!.r, fond!.g, fond!.b)[2]).toBeCloseTo(DARK_FLOOR, 2);
    expect(rgbToHsl(texte!.r, texte!.g, texte!.b)[2]).toBeCloseTo(DARK_CEILING, 2);
  });

  it('renverse l’ordre des gris sans en écraser aucun', () => {
    // L'IGN a réglé ses contrastes ; l'inversion doit les préserver, pas
    // les aplatir. Deux gris distincts restent distincts, dans l'ordre
    // inverse.
    const clairs = ['#FFFFFF', '#F2F2F2', '#CDCDCD', '#949494', '#505050'];
    const clartes = clairs.map((couleur) => {
      const sombre = parseColor(darkenColor(couleur));
      return rgbToHsl(sombre!.r, sombre!.g, sombre!.b)[2];
    });

    for (let index = 1; index < clartes.length; index += 1) {
      expect(clartes[index] as number).toBeGreaterThan(clartes[index - 1] as number);
    }
  });

  it('conserve l’alpha : un halo à 50 % change de côté, pas de force', () => {
    expect(darkenColor('rgba(255, 255, 255, 0.5)')).toMatch(/^rgba\(\d+, \d+, \d+, 0\.5\)$/);
  });

  it('plafonne la saturation pour que le décor ne parle pas', () => {
    // Le plafond s'applique en HSL et la couleur ressort sur huit bits par
    // canal : la saturation relue est celle du plafond à la quantification
    // près, jamais exactement lui.
    const vif = parseColor(darkenColor('#00A0FF'));
    expect(rgbToHsl(vif!.r, vif!.g, vif!.b)[1]).toBeCloseTo(MAX_SATURATION, 2);

    // En dessous du plafond, rien n'est retenu : un gris reste un gris.
    const gris = parseColor(darkenColor('#CDCDCD'));
    expect(rgbToHsl(gris!.r, gris!.g, gris!.b)[1]).toBe(0);
  });

  it('laisse intacte une chaîne qui n’est pas une couleur', () => {
    expect(darkenColor('interpolate')).toBe('interpolate');
  });
});

describe('toDarkVectorStyle', () => {
  const feuille = {
    version: 8,
    name: 'PLAN IGN gris',
    sources: { plan_ign: { type: 'vector' as const } },
    layers: [
      { id: 'bckgrd', type: 'fill', paint: { 'fill-color': '#FFFFFF', 'fill-opacity': 1 } },
      {
        id: 'routes',
        type: 'line',
        paint: {
          'line-color': ['interpolate', ['linear'], ['zoom'], 10, '#CDCDCD', 14, '#949494'],
          'line-width': 2,
          'line-dasharray': [2, 1],
        },
      },
      {
        id: 'toponymes',
        type: 'symbol',
        paint: { 'text-color': '#000000', 'text-halo-color': 'rgba(255, 255, 255, 0.5)' },
      },
      {
        id: 'ocs - Zone sable sec',
        type: 'fill',
        paint: { 'fill-pattern': 'Sable', 'fill-opacity': 1 },
      },
      { id: 'sans-peinture', type: 'background' },
    ],
  };

  it('éclaircit le texte et assombrit le fond', () => {
    const sombre = toDarkVectorStyle(feuille);
    const fond = sombre.layers[0]?.paint?.['fill-color'] as string;
    const texte = sombre.layers[2]?.paint?.['text-color'] as string;
    expect(parseColor(fond)!.r).toBeLessThan(40);
    expect(parseColor(texte)!.r).toBeGreaterThan(190);
  });

  it('descend au fond des expressions sans toucher aux opérateurs', () => {
    const sombre = toDarkVectorStyle(feuille);
    const expression = sombre.layers[1]?.paint?.['line-color'] as unknown[];
    expect(expression[0]).toBe('interpolate');
    expect(expression[1]).toEqual(['linear']);
    expect(expression[2]).toEqual(['zoom']);
    expect(expression[3]).toBe(10);
    expect(parseColor(expression[4] as string)!.r).toBeLessThan(100);
  });

  it('ne touche qu’aux propriétés de couleur', () => {
    const sombre = toDarkVectorStyle(feuille);
    expect(sombre.layers[1]?.paint?.['line-width']).toBe(2);
    expect(sombre.layers[1]?.paint?.['line-dasharray']).toEqual([2, 1]);
  });

  it('retourne le halo de texte : sombre derrière un texte clair', () => {
    const sombre = toDarkVectorStyle(feuille);
    const halo = parseColor(sombre.layers[2]?.paint?.['text-halo-color'] as string);
    expect(halo!.r).toBeLessThan(40);
    expect(halo!.a).toBe(0.5);
  });

  it('rabaisse les surfaces à motif, que le sprite empêche de recolorer', () => {
    const sombre = toDarkVectorStyle(feuille);
    expect(sombre.layers[3]?.paint?.['fill-pattern']).toBe('Sable');
    expect(sombre.layers[3]?.paint?.['fill-opacity']).toBe(PATTERN_OPACITY);
  });

  it('laisse passer une couche sans peinture', () => {
    expect(() => toDarkVectorStyle(feuille)).not.toThrow();
    expect(toDarkVectorStyle(feuille).layers[4]?.paint).toBeUndefined();
  });

  it('ne modifie pas la feuille d’origine', () => {
    // La feuille claire et la feuille sombre coexistent : la bascule de
    // thème rejoue la transformation sur la même source.
    toDarkVectorStyle(feuille);
    expect(feuille.layers[0]?.paint?.['fill-color']).toBe('#FFFFFF');
  });

  it('recopie tout ce qui n’est pas une couche', () => {
    const sombre = toDarkVectorStyle(feuille);
    expect(sombre.name).toBe('PLAN IGN gris');
    expect(sombre.sources).toEqual(feuille.sources);
    expect(sombre.version).toBe(8);
  });
});
