import 'server-only';

import type { SourceFreshness } from '@mapfeux/domain';

import { createPublicReadClient } from '@/lib/supabase/server';

/**
 * Lecture de l'état des sources depuis la vue `api.source_status`.
 * Alimente la page /statut et le bloc `meta.sources` de l'API. FR-110.
 */

export interface SourceStatusRow {
  key: string;
  name: string;
  provider: string;
  attribution: string;
  documentation_url: string | null;
  license_name: string | null;
  last_successful_import_at: string | null;
  last_data_at: string | null;
  freshness: SourceFreshness;
  incident_message: string | null;
  incident_opened_at: string | null;
}

/**
 * Résultat explicite plutôt qu'un simple tableau.
 *
 * « Aucune source connue » et « impossible de lire l'état des sources » sont
 * deux situations différentes qu'un tableau vide confond. Les confondre
 * conduirait /statut à annoncer que tout va bien alors que la page ne sait
 * rien — exactement la fausse assurance que le cahier §5.13 proscrit.
 */
export type SourceStatusResult =
  { readable: true; sources: SourceStatusRow[] } | { readable: false; sources: [] };

export async function fetchSourceStatus(): Promise<SourceStatusResult> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.from('source_status').select('*').order('key');

  if (error !== null) {
    // La page /statut doit rester affichable même si sa propre source de
    // vérité est injoignable : on annonce l'indisponibilité plutôt que de
    // faire échouer le rendu. FR-114
    console.error('[sources] lecture de api.source_status impossible', {
      code: error.code,
      message: error.message,
    });
    return { readable: false, sources: [] };
  }

  return { readable: true, sources: (data ?? []) as SourceStatusRow[] };
}

/** Réduit les lignes en bloc `meta.sources` pour les réponses de l'API. */
export function toMetaSources(
  rows: SourceStatusRow[],
): Record<string, { status: SourceFreshness; dataAt: string | null }> {
  return Object.fromEntries(
    rows.map((row) => [row.key, { status: row.freshness, dataAt: row.last_data_at }]),
  );
}
