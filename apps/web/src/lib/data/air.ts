import 'server-only';

import { fromArrayBuffer } from 'geotiff';

import { isStale, nearestCell, pickClosest } from '@/lib/air/sampling';
import { publicEnv } from '@/lib/env';
import { createPublicReadClient } from '@/lib/supabase/server';

/**
 * Consultation ponctuelle de la qualité de l'air modélisée.
 *
 * Référence : cahier v2.1 §19.2 et FR-121 ; plan J9.
 *
 * Le serveur échantillonne le COG de l'échéance la plus proche de
 * l'instant demandé — jamais la grille entière vers le navigateur (§19.1).
 * Le COG est un objet public au nom porteur de son empreinte : le fetch est
 * mis en cache indéfiniment, et l'empreinte est vérifiée à la lecture comme
 * partout ailleurs dans la chaîne.
 *
 * Une panne ici rend une liste vide, jamais une exception : la fiche
 * commune reste entière quand CAMS manque (FR-125).
 */

interface AirAssetRow {
  pollutant: string;
  unit: string;
  resolution: string;
  model: string;
  run_at: string;
  lead_hours: number;
  valid_at: string;
  asset_path: string;
  checksum: string;
}

export interface AirSample {
  pollutant: string;
  value: number;
  unit: string;
  resolution: string;
  model: string;
  runAt: string;
  validAt: string;
  samplingMethod: string;
  stale: boolean;
}

/** Méthode annoncée sur la fiche (§19.2 : elle fait partie de la réponse). */
export const AIR_SAMPLING_METHOD = 'cellule de grille la plus proche, échantillonnée serveur';

export async function fetchAirSamples(
  longitude: number,
  latitude: number,
  now: Date = new Date(),
): Promise<AirSample[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('air_grid_assets');

  if (error !== null) {
    console.error('[air] actifs illisibles', { code: error.code, message: error.message });
    return [];
  }

  const byPollutant = new Map<string, (AirAssetRow & { validAt: Date })[]>();
  for (const row of (data ?? []) as AirAssetRow[]) {
    const list = byPollutant.get(row.pollutant) ?? [];
    list.push({ ...row, validAt: new Date(row.valid_at) });
    byPollutant.set(row.pollutant, list);
  }

  const samples: AirSample[] = [];
  for (const [pollutant, assets] of byPollutant) {
    const chosen = pickClosest(assets, now);
    if (chosen === null) continue;

    try {
      const value = await sampleCog(chosen.asset_path, chosen.checksum, longitude, latitude);
      if (value === null) continue;
      samples.push({
        pollutant,
        value: Math.round(value * 10) / 10,
        unit: chosen.unit,
        resolution: chosen.resolution,
        model: chosen.model,
        runAt: chosen.run_at,
        validAt: chosen.validAt.toISOString(),
        samplingMethod: AIR_SAMPLING_METHOD,
        stale: isStale(chosen.validAt, now),
      });
    } catch (cause) {
      // FR-125 : l'indisponibilité d'un polluant ne bloque ni la page ni
      // l'autre polluant.
      console.error('[air] échantillonnage impossible', {
        pollutant,
        message: cause instanceof Error ? cause.message : String(cause),
      });
    }
  }

  return samples.sort((a, b) => a.pollutant.localeCompare(b.pollutant));
}

async function sampleCog(
  assetPath: string,
  checksum: string,
  longitude: number,
  latitude: number,
): Promise<number | null> {
  const url = `${publicEnv.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/${assetPath}`;
  // Le nom de l'objet porte son empreinte : il ne change jamais, le cache
  // peut être définitif.
  const response = await fetch(url, { cache: 'force-cache' });
  if (!response.ok) {
    throw new Error(`COG inaccessible (${response.status})`);
  }
  const buffer = await response.arrayBuffer();

  const digest = await crypto.subtle.digest('SHA-256', buffer);
  const actual = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  if (actual !== checksum) {
    throw new Error('empreinte du COG différente du registre');
  }

  const tiff = await fromArrayBuffer(buffer);
  const image = await tiff.getImage();
  const [originX, originY] = image.getOrigin();
  const [resolutionX, resolutionY] = image.getResolution();
  if (
    originX === undefined ||
    originY === undefined ||
    resolutionX === undefined ||
    resolutionY === undefined
  ) {
    throw new Error('géoréférencement du COG illisible');
  }

  const cell = nearestCell(
    {
      originX,
      originY,
      resolutionX,
      resolutionY,
      width: image.getWidth(),
      height: image.getHeight(),
    },
    longitude,
    latitude,
  );
  if (cell === null) return null;

  const rasters = await image.readRasters({
    window: [cell.column, cell.row, cell.column + 1, cell.row + 1],
  });
  const band = rasters[0];
  if (band === undefined) return null;
  const value = typeof band === 'number' ? band : Number(band[0]);
  return Number.isFinite(value) ? value : null;
}
