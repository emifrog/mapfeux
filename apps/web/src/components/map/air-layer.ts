import type maplibregl from 'maplibre-gl';

import { isStale, pickClosest } from '@/lib/air/sampling';
import { publicEnv } from '@/lib/env';

import { DEPARTMENTS_FILL_LAYER_ID } from './department-layer';
import { EVENTS_TAIL_LAYER_ID } from './event-layer';

/**
 * Couche raster de la qualité de l'air modélisée. Cahier §19.1 et FR-121.
 *
 * La carte lit l'alias `cams-{polluant}.json` — les métadonnées légères du
 * §19.1 — et affiche l'archive PMTiles de l'échéance la plus proche de
 * maintenant. La légende vient du même alias : c'est la palette versionnée
 * qui a réellement coloré les tuiles, jamais une copie côté front qui
 * divergerait à la première révision.
 *
 * Le rééchantillonnage est au **plus proche voisin** : les cellules de 0,1°
 * restent des cellules. Les lisser inventerait une précision que la grille
 * n'a pas — le même principe que l'échantillonnage de la fiche commune.
 */

export const AIR_SOURCE_ID = 'mapfeux-air';
export const AIR_LAYER_ID = 'mapfeux-air-raster';

export interface AirLegendBand {
  jusqu_a: number | null;
  couleur: string;
  libelle: string;
}

interface AirAlias {
  modele: string;
  polluant: string;
  unite: string;
  resolution: string;
  run: string;
  attribution: string;
  palette: { version: string; source: string; bandes: AirLegendBand[] };
  echeances: { echeance: number; valide_a: string; objet: string }[];
}

/** Ce que la légende et l'attribution ont besoin de savoir de la couche. */
export interface AirTilesInfo {
  pollutant: string;
  url: string;
  model: string;
  unit: string;
  resolution: string;
  runAt: string;
  validAt: string;
  paletteVersion: string;
  paletteSource: string;
  bands: AirLegendBand[];
  attribution: string;
}

const TILES_BASE = `${publicEnv.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/tiles`;

/**
 * Résout l'archive de tuiles à afficher pour un polluant, ou null.
 *
 * Null couvre trois cas d'un même geste : alias absent (source jamais
 * dérivée), alias illisible, ou dernière échéance au-delà du seuil de
 * péremption — une carte de la veille présentée comme actuelle serait un
 * mensonge coloré. L'appelant affiche alors « aucune donnée récente ».
 */
export async function resolveAirTiles(
  pollutant: string,
  now: Date = new Date(),
): Promise<AirTilesInfo | null> {
  try {
    const response = await fetch(`${TILES_BASE}/cams-${pollutant}.json`);
    if (!response.ok) return null;
    const alias = (await response.json()) as AirAlias;

    const chosen = pickClosest(
      alias.echeances.map((entry) => ({ ...entry, validAt: new Date(entry.valide_a) })),
      now,
    );
    if (chosen === null || isStale(chosen.validAt, now)) return null;

    return {
      pollutant: alias.polluant,
      url: `${TILES_BASE}/${chosen.objet}`,
      model: alias.modele,
      unit: alias.unite,
      resolution: alias.resolution,
      runAt: alias.run,
      validAt: chosen.valide_a,
      paletteVersion: alias.palette.version,
      paletteSource: alias.palette.source,
      bands: alias.palette.bandes,
      attribution: alias.attribution,
    };
  } catch {
    return null;
  }
}

/** La première couche au-dessus du fond : l'air se glisse sous tout le reste. */
function firstOverlayLayerId(map: maplibregl.Map): string | undefined {
  for (const layerId of [DEPARTMENTS_FILL_LAYER_ID, EVENTS_TAIL_LAYER_ID]) {
    if (map.getLayer(layerId) !== undefined) return layerId;
  }
  return undefined;
}

export function removeAirLayer(map: maplibregl.Map): void {
  if (map.getLayer(AIR_LAYER_ID) !== undefined) map.removeLayer(AIR_LAYER_ID);
  if (map.getSource(AIR_SOURCE_ID) !== undefined) map.removeSource(AIR_SOURCE_ID);
}

/**
 * Pose (ou remplace) la couche raster. Sous les lavis départementaux et les
 * événements : le champ modélisé est un contexte, jamais le sujet — les
 * détections restent au premier plan (§8.1).
 */
export function setAirLayer(map: maplibregl.Map, info: AirTilesInfo): void {
  removeAirLayer(map);

  map.addSource(AIR_SOURCE_ID, {
    type: 'raster',
    url: `pmtiles://${info.url}`,
    tileSize: 256,
    // L'archive s'arrête au zoom 6 — la grille de 0,1° n'a plus
    // d'information au-delà ; MapLibre sur-zoome le dernier niveau.
    maxzoom: 6,
    attribution: info.attribution,
  });

  map.addLayer(
    {
      id: AIR_LAYER_ID,
      type: 'raster',
      source: AIR_SOURCE_ID,
      paint: {
        'raster-opacity': 0.55,
        'raster-resampling': 'nearest',
      },
    },
    firstOverlayLayerId(map),
  );
}
