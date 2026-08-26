import { publicEnv } from '@/lib/env';
import {
  extentToCoordinates,
  selectFrames,
  type ImageCoordinates,
  type RadarAliasFrame,
} from '@/lib/radar/frames';

/**
 * Timeline radar : lecture de l'alias publié et frames prêtes à afficher.
 *
 * Référence : cahier v2.1 §16.6, §19.3, FR-123. La sélection elle-même —
 * filtre d'expiration contre l'horloge du lecteur, ordre chronologique —
 * vit dans `frames.ts`, pur et testé seul.
 */

export interface RadarBand {
  jusqu_a: number | null;
  couleur: string;
  libelle: string;
}

export interface RadarFrame {
  acquiredAt: Date;
  expiresAt: Date;
  url: string;
}

export type { ImageCoordinates };

export interface RadarTimeline {
  frames: RadarFrame[]; // non expirées, en ordre chronologique
  coordinates: ImageCoordinates;
  unit: string;
  quantityLabel: string;
  paletteVersion: string;
  paletteSource: string;
  drawnFrom: number;
  bands: RadarBand[];
  attribution: string;
}

interface RadarAlias {
  grandeur: string;
  attribution: string;
  palette: {
    version: string;
    source: string;
    unite: string;
    seuil_trace: number;
    bandes: RadarBand[];
  };
  emprise: [number, number, number, number]; // ouest, sud, est, nord
  frames: RadarAliasFrame[];
}

const TILES_BASE = `${publicEnv.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/tiles`;

/**
 * Résout la timeline servable, ou null.
 *
 * Null couvre d'un même geste l'alias absent (source jamais importée),
 * illisible, et la timeline vide (toutes les frames expirées — le cron
 * s'est tu plus de deux heures). L'appelant affiche alors « aucune donnée
 * récente » : l'indisponibilité du radar ne touche rien d'autre (FR-125).
 */
export async function resolveRadarTimeline(now: Date = new Date()): Promise<RadarTimeline | null> {
  try {
    const response = await fetch(`${TILES_BASE}/radar-lame-d-eau.json`);
    if (!response.ok) return null;
    const alias = (await response.json()) as RadarAlias;

    const selected = selectFrames(alias.frames, now);
    if (selected.length === 0) return null;

    return {
      frames: selected.map((frame) => ({
        acquiredAt: frame.acquiredAt,
        expiresAt: frame.expiresAt,
        url: `${TILES_BASE}/${frame.objet}`,
      })),
      coordinates: extentToCoordinates(alias.emprise),
      unit: alias.palette.unite,
      quantityLabel: alias.grandeur,
      paletteVersion: alias.palette.version,
      paletteSource: alias.palette.source,
      drawnFrom: alias.palette.seuil_trace,
      bands: alias.palette.bandes,
      attribution: alias.attribution,
    };
  } catch {
    return null;
  }
}
