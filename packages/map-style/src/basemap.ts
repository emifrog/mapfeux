/**
 * Fond cartographique.
 *
 * Référence : cahier §8.3 et §9.5.
 *
 * Le fond provient de la Géoplateforme IGN, dont l'attribution est obligatoire
 * et doit rester visible en permanence (§9.5). Le style est construit ici, hors
 * de tout composant React, afin d'être vérifiable sans navigateur.
 *
 * Choix d'un fond raster plutôt que vectoriel : le raster IGN est disponible
 * sans clé et sans négociation de licence supplémentaire, ce qui convient au
 * pilote. Le passage au vectoriel — meilleure lisibilité au zoom, thème sombre
 * possible — relève de la phase 2.
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
