/**
 * Variante sombre du fond vectoriel, dérivée de la feuille servie par l'IGN.
 *
 * Référence : cahier §6.5 (thème) et §8.1 (l'orange appartient à
 * l'observation thermique).
 *
 * ## Pourquoi dériver plutôt que choisir
 *
 * La Géoplateforme publie `standard`, `gris`, `attenue`, `classique`,
 * `epure` et `accentue` — sondés le 11 septembre 2026, tous clairs.
 * `sombre`, `dark` et `nuit` répondent 404 : il n'existe pas de fond
 * sombre à demander. Le site, lui, a un thème sombre depuis la refonte,
 * et servait jusqu'ici un rectangle blanc au milieu d'une page bleu nuit.
 *
 * La feuille est un JSON de 425 couches qu'on charge de toute façon. La
 * transformer avant de la remettre à MapLibre coûte un parcours ; la
 * recopier à la main coûterait de la maintenir contre une feuille qui
 * évolue sans nous.
 *
 * ## Ce que fait la transformation
 *
 * Elle **inverse la clarté** et laisse tout le reste en place : géométrie,
 * filtres, seuils de zoom, épaisseurs, tiretés. La feuille `gris` est
 * intégralement en gris neutres — vérifié, les 525 couleurs qu'elle
 * déclare ont leurs trois canaux égaux — si bien qu'inverser la clarté
 * préserve exactement les écarts de contraste voulus par l'IGN : ce qui
 * se distinguait se distingue encore, dans l'autre sens.
 *
 * Deux bornes plutôt qu'une inversion franche. Le blanc ne devient pas
 * noir mais `DARK_FLOOR`, le noir ne devient pas blanc mais `DARK_CEILING` :
 * un fond parfaitement noir ferait des marqueurs orange des trous de
 * lumière, et un texte parfaitement blanc entrerait en concurrence avec
 * eux. Le fond doit se retirer dans les deux thèmes.
 *
 * La saturation est plafonnée pour le cas où l'IGN colorerait la feuille,
 * ou pour `standard` : une inversion de clarté conserve la teinte, et une
 * teinte saturée reste une couleur qui parle à côté de l'orange.
 */

/** Couleur décomposée, canaux en 0-255 et alpha en 0-1. */
export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

/** Clarté du blanc transformé : le fond de carte, presque noir. */
export const DARK_FLOOR = 0.07;

/** Clarté du noir transformé : le texte, gris clair et non blanc. */
export const DARK_CEILING = 0.82;

/** Au-delà, une teinte cesse d'être un décor et devient un propos. */
export const MAX_SATURATION = 0.3;

/**
 * Opacité des surfaces à motif dans le thème sombre.
 *
 * Le sprite est clair : sur un fond presque noir, une plage ou un marais
 * rendus à pleine opacité brillent plus que les détections, ce qui
 * renverse la hiérarchie de lecture (§8.1). À cette valeur, la texture
 * se devine sans se disputer l'attention.
 */
export const PATTERN_OPACITY = 0.28;

const HEX_SHORT = /^#([0-9a-f])([0-9a-f])([0-9a-f])([0-9a-f])?$/i;
const HEX_LONG = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})?$/i;
const FUNCTIONAL = /^(rgb|rgba|hsl|hsla)\(([^)]*)\)$/i;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Décompose une couleur CSS telle que MapLibre les accepte dans une
 * feuille de style : hexadécimal court ou long, avec ou sans alpha, et
 * les formes fonctionnelles `rgb()`, `rgba()`, `hsl()`, `hsla()`.
 *
 * Rend `null` sur tout ce qui n'est pas reconnu — un nom CSS (`white`),
 * une chaîne qui n'était pas une couleur. L'appelant laisse alors la
 * valeur intacte : mieux vaut une couleur non transformée qu'une couleur
 * inventée.
 */
export function parseColor(value: string): Rgba | null {
  const text = value.trim();

  const short = HEX_SHORT.exec(text);
  if (short !== null) {
    const [, r, g, b, a] = short;
    const double = (hex: string): number => parseInt(hex + hex, 16);
    return {
      r: double(r as string),
      g: double(g as string),
      b: double(b as string),
      a: a === undefined ? 1 : double(a) / 255,
    };
  }

  const long = HEX_LONG.exec(text);
  if (long !== null) {
    const [, r, g, b, a] = long;
    return {
      r: parseInt(r as string, 16),
      g: parseInt(g as string, 16),
      b: parseInt(b as string, 16),
      a: a === undefined ? 1 : parseInt(a, 16) / 255,
    };
  }

  const functional = FUNCTIONAL.exec(text);
  if (functional === null) return null;

  const kind = (functional[1] as string).toLowerCase();
  const parts = (functional[2] as string)
    .split(/[\s,/]+/)
    .filter((part) => part.length > 0)
    .map((part) => (part.endsWith('%') ? Number(part.slice(0, -1)) / 100 : Number(part)));

  if (parts.length < 3 || parts.some((part) => Number.isNaN(part))) return null;
  const alpha = parts[3] === undefined ? 1 : clamp(parts[3], 0, 1);

  if (kind === 'rgb' || kind === 'rgba') {
    return {
      r: clamp(parts[0] as number, 0, 255),
      g: clamp(parts[1] as number, 0, 255),
      b: clamp(parts[2] as number, 0, 255),
      a: alpha,
    };
  }

  // `hsl(210 40% 50%)` : la teinte est en degrés, les deux autres en
  // pourcentage — déjà ramenés en 0-1 par la division ci-dessus.
  const { r, g, b } = hslToRgb(
    ((parts[0] as number) % 360) / 360,
    clamp(parts[1] as number, 0, 1),
    clamp(parts[2] as number, 0, 1),
  );
  return { r, g, b, a: alpha };
}

/** Réécrit une couleur sous la forme que MapLibre relira sans ambiguïté. */
export function formatColor(color: Rgba): string {
  const channel = (value: number): number => Math.round(clamp(value, 0, 255));
  const { r, g, b } = { r: channel(color.r), g: channel(color.g), b: channel(color.b) };
  if (color.a >= 1) {
    const hex = (value: number): string => value.toString(16).padStart(2, '0');
    return `#${hex(r)}${hex(g)}${hex(b)}`;
  }
  return `rgba(${r}, ${g}, ${b}, ${Number(color.a.toFixed(3))})`;
}

/** Teinte, saturation et clarté, toutes trois en 0-1. */
export function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const red = r / 255;
  const green = g / 255;
  const blue = b / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const lightness = (max + min) / 2;

  if (max === min) return [0, 0, lightness];

  const delta = max - min;
  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min);

  let hue: number;
  if (max === red) {
    hue = (green - blue) / delta + (green < blue ? 6 : 0);
  } else if (max === green) {
    hue = (blue - red) / delta + 2;
  } else {
    hue = (red - green) / delta + 4;
  }

  return [hue / 6, saturation, lightness];
}

export function hslToRgb(h: number, s: number, l: number): { r: number; g: number; b: number } {
  if (s === 0) {
    const grey = l * 255;
    return { r: grey, g: grey, b: grey };
  }

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;

  const component = (t: number): number => {
    let value = t;
    if (value < 0) value += 1;
    if (value > 1) value -= 1;
    if (value < 1 / 6) return p + (q - p) * 6 * value;
    if (value < 1 / 2) return q;
    if (value < 2 / 3) return p + (q - p) * (2 / 3 - value) * 6;
    return p;
  };

  return {
    r: component(h + 1 / 3) * 255,
    g: component(h) * 255,
    b: component(h - 1 / 3) * 255,
  };
}

/**
 * Transforme une couleur de la feuille claire en son équivalent sombre.
 *
 * L'alpha est conservé tel quel : un halo de texte à 50 % reste à 50 %,
 * il change seulement de côté — blanc derrière du texte noir, sombre
 * derrière du texte clair.
 *
 * Une chaîne non reconnue revient inchangée.
 */
export function darkenColor(value: string): string {
  const color = parseColor(value);
  if (color === null) return value;

  const [hue, saturation, lightness] = rgbToHsl(color.r, color.g, color.b);
  const inverted = DARK_FLOOR + (1 - lightness) * (DARK_CEILING - DARK_FLOOR);
  const { r, g, b } = hslToRgb(hue, Math.min(saturation, MAX_SATURATION), inverted);

  return formatColor({ r, g, b, a: color.a });
}

/**
 * Les propriétés de peinture de MapLibre qui portent une couleur se
 * terminent toutes par `-color`, sans exception dans la spécification du
 * style v8. Se fier au nom plutôt qu'à une liste close évite qu'une
 * propriété nouvelle passe au travers en silence.
 */
function isColorProperty(name: string): boolean {
  return name.endsWith('-color');
}

/**
 * Applique la transformation partout dans une valeur de peinture, y
 * compris au fond des expressions.
 *
 * Une propriété de couleur n'est pas toujours une chaîne : la feuille
 * `gris` en déclare 62 sous forme d'expression — `interpolate`, `match`,
 * `case` — où les couleurs sont mêlées à des seuils numériques et à des
 * noms d'opérateurs. Seules les chaînes reconnues comme couleurs sont
 * touchées ; `'interpolate'`, `'linear'` ou `'zoom'` n'en sont pas, et
 * `parseColor` les rend telles quelles.
 */
function darkenPaintValue(value: unknown): unknown {
  if (typeof value === 'string') return darkenColor(value);
  if (Array.isArray(value)) return value.map(darkenPaintValue);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, inner]) => [
        key,
        darkenPaintValue(inner),
      ]),
    );
  }
  return value;
}

/** Forme minimale attendue d'une feuille de style : le reste est recopié. */
interface StyleLike {
  layers?: { paint?: Record<string, unknown> }[];
}

/**
 * Rend une copie sombre de la feuille, sans modifier l'originale.
 *
 * ## Ce qui n'est pas transformé, et pourquoi
 *
 * Les dix couches à `fill-pattern` — marais, sable, graviers, glacier,
 * cimetière — sont peintes avec une image du sprite, que rien ne permet
 * de recolorer côté client. Leur opacité est rabaissée pour qu'une plage
 * ne devienne pas une tache de lumière sur une carte sombre ; la texture
 * reste lisible de près, où elle sert.
 */
export function toDarkVectorStyle<T extends StyleLike>(style: T): T {
  const layers = (style.layers ?? []).map((layer) => {
    const paint = layer.paint;
    if (paint === undefined) return layer;

    const darkened: Record<string, unknown> = {};
    for (const [property, value] of Object.entries(paint)) {
      darkened[property] = isColorProperty(property) ? darkenPaintValue(value) : value;
    }

    if (typeof paint['fill-pattern'] === 'string') {
      darkened['fill-opacity'] = PATTERN_OPACITY;
    }

    return { ...layer, paint: darkened };
  });

  return { ...style, layers };
}
