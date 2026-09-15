import 'server-only';

import { createPublicReadClient } from '@/lib/supabase/server';

import { readable, unreadable, type ReadResult } from './read-result';

/**
 * Accès aux communes.
 *
 * Référence : cahier §5.3 (FR-020 à FR-026) et §15.2.
 *
 * Le code INSEE est l'identifiant de référence. Le nom et le code postal ne
 * servent qu'à la recherche : plusieurs communes partagent un code postal, et
 * les homonymes sont fréquents (§5.3, FR-021).
 */

interface MunicipalityRow {
  insee_code: string;
  name: string;
  department_code: string;
  department_name: string | null;
  department_slug: string | null;
  postal_codes: string[];
  longitude: number;
  latitude: number;
  area_km2: number | null;
  source_version: string;
}

export interface Municipality {
  insee: string;
  name: string;
  departmentCode: string;
  departmentName: string | null;
  departmentSlug: string | null;
  postalCodes: string[];
  centroid: { longitude: number; latitude: number };
  areaKm2: number | null;
  sourceVersion: string;
}

interface SearchRow {
  insee_code: string;
  name: string;
  department_code: string;
  postal_codes: string[];
  longitude: number;
  latitude: number;
}

export interface MunicipalitySearchResult {
  insee: string;
  name: string;
  departmentCode: string;
  postalCodes: string[];
  centroid: { longitude: number; latitude: number };
}

function toMunicipality(row: MunicipalityRow): Municipality {
  return {
    insee: row.insee_code,
    name: row.name,
    departmentCode: row.department_code,
    departmentName: row.department_name,
    departmentSlug: row.department_slug,
    postalCodes: row.postal_codes,
    centroid: { longitude: row.longitude, latitude: row.latitude },
    areaKm2: row.area_km2 === null ? null : Number(row.area_km2),
    sourceVersion: row.source_version,
  };
}

/**
 * `null` si la commune n'existe pas ; `readable: false` si la base n'a pas
 * répondu — la page commune répondait 404 sur une panne, comme si la commune
 * n'existait pas (audit du 15 septembre 2026, même patron que les événements).
 */
export async function fetchMunicipality(insee: string): Promise<ReadResult<Municipality | null>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase
    .from('municipalities')
    .select('*')
    .eq('insee_code', insee)
    .maybeSingle();

  if (error !== null) {
    console.error('[municipalities] lecture impossible', {
      insee,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  return readable(data === null ? null : toMunicipality(data as MunicipalityRow));
}

/**
 * Recherche tolérante, déléguée à la fonction SQL `api.search_municipalities`
 * qui exploite l'index trigramme. Cible : p95 sous 300 ms (§6.2).
 */
export async function searchMunicipalities(
  query: string,
  limit: number,
): Promise<ReadResult<MunicipalitySearchResult[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('search_municipalities', {
    q: query,
    max_results: limit,
  });

  if (error !== null) {
    // Longtemps une exception (`SEARCH_UNAVAILABLE`) que la route attrapait :
    // le résultat explicite dit la même chose sans dérouter le flot.
    console.error('[municipalities] recherche impossible', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  return readable(
    ((data ?? []) as SearchRow[]).map((row) => ({
      insee: row.insee_code,
      name: row.name,
      departmentCode: row.department_code,
      postalCodes: row.postal_codes,
      centroid: { longitude: row.longitude, latitude: row.latitude },
    })),
  );
}

export interface ResolvedMunicipality {
  insee: string;
  name: string;
  departmentCode: string;
}

/**
 * Résout la commune contenant un point.
 *
 * Les coordonnées transmises ne sont ni journalisées, ni conservées : seule la
 * commune résolue est renvoyée. Cahier §22.2.
 */
export async function resolveMunicipality(
  longitude: number,
  latitude: number,
): Promise<ReadResult<ResolvedMunicipality | null>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('resolve_municipality', {
    lon: longitude,
    lat: latitude,
  });

  if (error !== null) {
    // Volontairement sans les coordonnées : elles ne doivent jamais atteindre
    // un fichier de journal (§23.1).
    console.error('[municipalities] résolution impossible', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  const rows = (data ?? []) as { insee_code: string; name: string; department_code: string }[];
  const first = rows[0];
  if (first === undefined) return readable(null);

  return readable({
    insee: first.insee_code,
    name: first.name,
    departmentCode: first.department_code,
  });
}
