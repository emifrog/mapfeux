import 'server-only';

import { createPublicReadClient } from '@/lib/supabase/server';

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

export async function fetchMunicipality(insee: string): Promise<Municipality | null> {
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
    return null;
  }

  return data === null ? null : toMunicipality(data as MunicipalityRow);
}

/**
 * Recherche tolérante, déléguée à la fonction SQL `api.search_municipalities`
 * qui exploite l'index trigramme. Cible : p95 sous 300 ms (§6.2).
 */
export async function searchMunicipalities(
  query: string,
  limit: number,
): Promise<MunicipalitySearchResult[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('search_municipalities', {
    q: query,
    max_results: limit,
  });

  if (error !== null) {
    console.error('[municipalities] recherche impossible', {
      code: error.code,
      message: error.message,
    });
    throw new Error('SEARCH_UNAVAILABLE');
  }

  return ((data ?? []) as SearchRow[]).map((row) => ({
    insee: row.insee_code,
    name: row.name,
    departmentCode: row.department_code,
    postalCodes: row.postal_codes,
    centroid: { longitude: row.longitude, latitude: row.latitude },
  }));
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
): Promise<ResolvedMunicipality | null> {
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
    throw new Error('RESOLVE_UNAVAILABLE');
  }

  const rows = (data ?? []) as { insee_code: string; name: string; department_code: string }[];
  const first = rows[0];
  if (first === undefined) return null;

  return {
    insee: first.insee_code,
    name: first.name,
    departmentCode: first.department_code,
  };
}
