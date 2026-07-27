import 'server-only';

import type { TerritoryStatus, TerritoryType } from '@mapfeux/domain';

import { createPublicReadClient } from '@/lib/supabase/server';

/**
 * Accès aux territoires.
 *
 * Référence : cahier §5.2 et §15.2.
 *
 * Ce module est la seule porte d'entrée vers `api.territories` : les pages
 * rendues côté serveur et les routes `/api/v1` l'utilisent toutes les deux,
 * plutôt que la page n'appelle sa propre API par HTTP. Un aller-retour réseau
 * vers son propre serveur ajoute de la latence et un mode de panne pour rien.
 */

/** Ligne brute de la vue `api.territories`. */
interface TerritoryRow {
  slug: string;
  code: string;
  type: TerritoryType;
  name: string;
  short_name: string | null;
  parent_slug: string | null;
  status: TerritoryStatus;
  timezone: string;
  center_longitude: number;
  center_latitude: number;
  default_zoom: number;
}

export interface Territory {
  slug: string;
  code: string;
  type: TerritoryType;
  name: string;
  shortName: string | null;
  parentSlug: string | null;
  status: TerritoryStatus;
  timezone: string;
  center: { longitude: number; latitude: number };
  defaultZoom: number;
}

export interface OfficialLink {
  category: string;
  title: string;
  url: string;
  organisation: string;
}

function toTerritory(row: TerritoryRow): Territory {
  return {
    slug: row.slug,
    code: row.code,
    type: row.type,
    name: row.name,
    shortName: row.short_name,
    parentSlug: row.parent_slug,
    status: row.status,
    timezone: row.timezone,
    center: { longitude: row.center_longitude, latitude: row.center_latitude },
    defaultZoom: Number(row.default_zoom),
  };
}

export async function fetchTerritories(): Promise<Territory[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase
    .from('territories')
    .select('*')
    .order('type')
    .order('name');

  if (error !== null) {
    console.error('[territories] lecture impossible', { code: error.code, message: error.message });
    return [];
  }

  return ((data ?? []) as TerritoryRow[]).map(toTerritory);
}

/** Retourne `null` si le territoire n'existe pas ou n'est pas encore ouvert. */
export async function fetchTerritory(slug: string): Promise<Territory | null> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase
    .from('territories')
    .select('*')
    .eq('slug', slug)
    .maybeSingle();

  if (error !== null) {
    console.error('[territories] lecture impossible', {
      slug,
      code: error.code,
      message: error.message,
    });
    return null;
  }

  return data === null ? null : toTerritory(data as TerritoryRow);
}

/**
 * Liens officiels d'un territoire. Cahier §5.12.
 *
 * L'absence de liens n'est pas une erreur : un territoire nouvellement ouvert
 * n'en a pas encore. La page doit le dire plutôt que d'échouer.
 */
export async function fetchOfficialLinks(territorySlug: string): Promise<OfficialLink[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase
    .from('official_links')
    .select('category, title, url, organisation, display_order')
    .eq('territory_slug', territorySlug)
    .order('display_order');

  if (error !== null) {
    console.error('[official-links] lecture impossible', {
      territorySlug,
      code: error.code,
      message: error.message,
    });
    return [];
  }

  return (data ?? []) as OfficialLink[];
}
