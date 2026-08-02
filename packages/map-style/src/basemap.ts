/**
 * Fond cartographique.
 *
 * Référence : cahier §8.3 et §9.5.
 *
 * Le fond provient de la Géoplateforme IGN, dont l'attribution est obligatoire
 * et doit rester visible en permanence (§9.5). Le style est construit ici, hors
 * de tout composant React, afin d'être vérifiable sans navigateur.
 *
 * Le fond par défaut est **vectoriel**, style « gris » publié par l'IGN. Une
 * première version retenait le raster au motif qu'il était seul disponible sans
 * clé ; vérification faite, le vectoriel l'est aussi, styles compris. Le motif
 * ne tenait donc plus.
 *
 * Le gris n'est pas une préférence esthétique. La carte doit se retirer devant
 * la donnée : sur un fond en couleurs, l'orange des détections entre en
 * concurrence avec les routes, les zones urbaines et les forêts, et le repérage
 * se fait au prix d'un effort. §8.1
 *
 * Le raster reste exposé, comme repli si la Géoplateforme changeait son offre
 * vectorielle, et pour l'orthophoto qui n'a pas d'équivalent vectoriel.
 */

/** Couches Géoplateforme utilisables comme fond. */
export const IGN_BASEMAP_LAYERS = {
  plan: 'GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2',
  orthophoto: 'ORTHOIMAGERY.ORTHOPHOTOS',
} as const;

export type IgnBasemapLayer = keyof typeof IGN_BASEMAP_LAYERS;

export const IGN_ATTRIBUTION = '© <a href="https://www.ign.fr/">IGN</a> — Géoplateforme';

const GEOPLATEFORME_WMTS = 'https://data.geopf.fr/wmts';

/** Construit l'URL de tuile WMTS attendue par MapLibre. */
export function ignTileUrl(layer: IgnBasemapLayer, format = 'image/png'): string {
  const params = new URLSearchParams({
    SERVICE: 'WMTS',
    REQUEST: 'GetTile',
    VERSION: '1.0.0',
    LAYER: IGN_BASEMAP_LAYERS[layer],
    STYLE: 'normal',
    TILEMATRIXSET: 'PM',
    FORMAT: format,
  });

  // MapLibre substitue lui-même {z}/{y}/{x} : les accolades ne doivent donc pas
  // être encodées, ce que ferait URLSearchParams. On les ajoute après coup.
  return `${GEOPLATEFORME_WMTS}?${params.toString()}&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}`;
}

/** Style MapLibre minimal, sans dépendance à un fichier de style distant. */
export function buildIgnBasemapStyle(layer: IgnBasemapLayer = 'plan') {
  const isPhoto = layer === 'orthophoto';

  return {
    version: 8 as const,
    sources: {
      'ign-basemap': {
        type: 'raster' as const,
        tiles: [ignTileUrl(layer, isPhoto ? 'image/jpeg' : 'image/png')],
        tileSize: 256,
        maxzoom: 19,
        attribution: IGN_ATTRIBUTION,
      },
    },
    layers: [
      {
        id: 'ign-basemap',
        type: 'raster' as const,
        source: 'ign-basemap',
        // Le fond reste discret : la lisibilité appartient aux détections, pas
        // au décor. §8.1
        paint: { 'raster-opacity': isPhoto ? 1 : 0.9 },
      },
    ],
  };
}

export type BasemapStyle = ReturnType<typeof buildIgnBasemapStyle>;

/**
 * Styles vectoriels publiés par la Géoplateforme, utilisables sans clé.
 *
 * `gris` est le fond par défaut : il laisse la palette d'âge des détections
 * seule porteuse de couleur. `standard` reste disponible pour qui cherche un
 * repère — un nom de rue, une limite de commune — plutôt qu'un feu.
 */
export const IGN_VECTOR_STYLES = {
  gris: 'https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/gris.json',
  standard:
    'https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/standard.json',
} as const;

export type IgnVectorStyle = keyof typeof IGN_VECTOR_STYLES;

/**
 * URL de style vectoriel, à passer telle quelle à MapLibre.
 *
 * MapLibre sait charger un style distant ; le construire à la main reviendrait
 * à recopier plusieurs centaines de définitions de couches, qui évolueraient
 * sans nous.
 */
export function ignVectorStyleUrl(style: IgnVectorStyle = 'gris'): string {
  return IGN_VECTOR_STYLES[style];
}
