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

export async function fetchSourceStatus(): Promise<SourceStatusRow[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.from('source_status').select('*').order('key');

  if (error !== null) {
    // La page /statut doit rester affichable même si sa propre source de
    // vérité est injoignable : on renvoie une liste vide plutôt que de faire
    // échouer le rendu, et l'appelant affiche l'indisponibilité. FR-114
    console.error('[sources] lecture de api.source_status impossible', {
      code: error.code,
      message: error.message,
    });
    return [];
  }

  return (data ?? []) as SourceStatusRow[];
}

/** Réduit les lignes en bloc `meta.sources` pour les réponses de l'API. */
export function toMetaSources(
  rows: SourceStatusRow[],
): Record<string, { status: SourceFreshness; dataAt: string | null }> {
  return Object.fromEntries(
    rows.map((row) => [row.key, { status: row.freshness, dataAt: row.last_data_at }]),
  );
}
