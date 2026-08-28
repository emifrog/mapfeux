import 'server-only';

import { createPublicReadClient } from '@/lib/supabase/server';

/**
 * Citations officielles captées en liste blanche. ADR-026, cahier §20.4.
 *
 * Ce que la couche rend est ce que l'autorité a publié : titre verbatim,
 * lien vers la source, organisme, date. Le rapprochement à un événement
 * est un appariement de structure — commune mentionnée, fenêtre
 * temporelle — jamais une lecture du texte (§2.4).
 */

interface DepartmentItemRow {
  organisation: string;
  title: string;
  url: string;
  published_on: string | null;
}

export interface OfficialItem {
  organisation: string;
  title: string;
  url: string;
  publishedOn: string | null;
}

export async function fetchDepartmentOfficialItems(
  departmentCode: string,
): Promise<OfficialItem[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('department_official_items', {
    department: departmentCode,
  });

  if (error !== null) {
    // FR-125, même doctrine : une capture indisponible ne condamne pas la
    // page — la section affichera son absence.
    console.error('[officiel] citations illisibles', {
      departmentCode,
      code: error.code,
      message: error.message,
    });
    return [];
  }

  return ((data ?? []) as DepartmentItemRow[]).map((row) => ({
    organisation: row.organisation,
    title: row.title,
    url: row.url,
    publishedOn: row.published_on,
  }));
}

interface EventItemRow extends DepartmentItemRow {
  municipality_name: string;
}

export interface EventOfficialItem extends OfficialItem {
  municipalityName: string;
}

export async function fetchEventOfficialItems(publicId: string): Promise<EventOfficialItem[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_official_items', {
    event_public_id: publicId,
  });

  if (error !== null) {
    console.error('[officiel] rapprochement illisible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return [];
  }

  return ((data ?? []) as EventItemRow[]).map((row) => ({
    organisation: row.organisation,
    title: row.title,
    url: row.url,
    publishedOn: row.published_on,
    municipalityName: row.municipality_name,
  }));
}
