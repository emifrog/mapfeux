/**
 * Produit favicon.ico et apple-icon.png à partir de src/app/icon.svg.
 *
 * Les deux fichiers sont versionnés et Next les sert tels quels : ce script ne
 * tourne qu'après une retouche du dessin, jamais à la construction.
 *
 *   node scripts/build-icons.mjs      (depuis apps/web)
 *
 * `sharp` n'est pas une dépendance de l'application : il est résolu depuis
 * `next`, qui l'embarque pour l'optimisation d'images, pnpm ne l'exposant pas
 * directement à apps/web.
 *
 * Le moteur de rendu ignore `prefers-color-scheme` : sans intervention, le
 * dessin sort aux couleurs du thème clair. C'est ce que veut le .ico, qui ne
 * suit pas le thème de toute façon.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const sharp = createRequire(require.resolve('next/package.json'))('sharp');

const APP = new URL('../src/app/', import.meta.url);
const svg = await readFile(new URL('icon.svg', APP), 'utf8');

/**
 * Rendu direct à la taille cible : 300 unités de viewBox valent `size` pixels.
 * Réduire un grand rendu adoucit l'anneau, qui tient en un pixel à 16 px.
 */
function render(source, size) {
  return sharp(Buffer.from(source), { density: (72 * size) / 300 }).resize(size, size);
}

/**
 * ICO à images PNG, lu par tous les navigateurs actuels.
 *
 * 32 en tête : Next tire l'attribut `sizes` du lien de la première image. Un
 * .ico annoncé plus grand que 32 px ferait préférer l'ICO au SVG par Chrome.
 */
async function ico(sizes) {
  const images = await Promise.all(sizes.map((s) => render(svg, s).png().toBuffer()));
  const header = Buffer.alloc(6 + 16 * images.length);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  let offset = header.length;
  images.forEach((png, i) => {
    const entry = 6 + 16 * i;
    header.writeUInt8(sizes[i] % 256, entry);
    header.writeUInt8(sizes[i] % 256, entry + 1);
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(png.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += png.length;
  });
  return Buffer.concat([header, ...images]);
}

await writeFile(new URL('favicon.ico', APP), await ico([32, 16]));

/**
 * Icône d'écran d'accueil : la déclinaison « application » de la planche
 * d'identité — dessin clair sur tuile bleu nuit. iOS veut un fond opaque : un
 * fond transparent y devient noir.
 *
 * Les couleurs sombres sont celles de icon.svg, recopiées hors de leur requête
 * média pour s'appliquer. À 180 px, le graticule du logo redevient lisible :
 * il revient, repris de components/logo.tsx.
 */
const DARK_RULES = svg.match(/@media \(prefers-color-scheme: dark\) \{([\s\S]*?)\}\s*<\/style>/)[1];
const GRATICULE = `
  <g fill="none" stroke="#77828e" stroke-width="5">
    <path d="M89 119 A66 66 0 0 1 132 75" />
    <path d="M145 71 A66 66 0 0 1 207 108" />
    <path d="M211 122 A66 66 0 0 1 211 155" />
    <path d="M89 157 A66 66 0 0 1 89 124" />
    <path d="M79 138 H105" />
    <path d="M195 138 H221" />
    <path d="M150 67 V91" />
  </g>`;
const appSvg = svg.replace('</style>', `${DARK_RULES}</style>`).replace('</g>', `</g>${GRATICULE}`);

// iOS arrondit les coins de l'icône : le dessin garde une marge de 22 px.
const APPLE = 180;
const INNER = 136;
const apple = await sharp({
  create: { width: APPLE, height: APPLE, channels: 3, background: '#021526' },
})
  .composite([
    {
      input: await render(appSvg, INNER).png().toBuffer(),
      left: (APPLE - INNER) / 2,
      top: (APPLE - INNER) / 2,
    },
  ])
  .png()
  .toBuffer();
await writeFile(new URL('apple-icon.png', APP), apple);

console.log('favicon.ico et apple-icon.png écrits dans src/app/');
