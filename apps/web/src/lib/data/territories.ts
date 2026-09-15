import 'server-only';

import type { TerritoryStatus, TerritoryType } from '@mapfeux/domain';

import { createPublicReadClient } from '@/lib/supabase/server';

import { readable, unreadable, type ReadResult } from './read-result';

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

/**
 * Les territoires ouverts ou pilotes. Non lus, ils ne sont pas « aucun » :
 * l'accueil faisait disparaître sa section « Territoires ouverts » sur une
 * panne, et l'API répondait une liste vide mise en cache une heure.
 */
export async function fetchTerritories(): Promise<ReadResult<Territory[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase
    .from('territories')
    .select('*')
    .order('type')
    .order('name');

  if (error !== null) {
    console.error('[territories] lecture impossible', { code: error.code, message: error.message });
    return unreadable();
  }

  return readable(((data ?? []) as TerritoryRow[]).map(toTerritory));
}

/**
 * `null` si le territoire n'existe pas ou n'est pas encore ouvert ;
 * `readable: false` si la base n'a pas répondu — ce n'est pas un 404.
 */
export async function fetchTerritory(slug: string): Promise<ReadResult<Territory | null>> {
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
    return unreadable();
  }

  return readable(data === null ? null : toTerritory(data as TerritoryRow));
}

/**
 * Liens officiels d'un territoire. Cahier §5.12.
 *
 * L'absence de liens n'est pas une erreur : un territoire nouvellement ouvert
 * n'en a pas encore. La page doit le dire plutôt que d'échouer — et dire
 * autre chose quand elle n'a pas pu lire : « aucun lien » sur une panne
 * enverrait le lecteur chercher ailleurs des liens qui existent.
 */
export async function fetchOfficialLinks(
  territorySlug: string,
): Promise<ReadResult<OfficialLink[]>> {
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
    return unreadable();
  }

  return readable((data ?? []) as OfficialLink[]);
}
