import 'server-only';

import type { createPublicServerClient } from '@/lib/supabase/server';

type SessionClient = Awaited<ReturnType<typeof createPublicServerClient>>;

/**
 * Profil administrateur de l'utilisateur connecté.
 *
 * Référence : cahier §14.1 et §14.2.
 *
 * Le rôle vit dans `admin.profiles`, jamais dans les métadonnées du jeton : un
 * jeton ne doit pas pouvoir s'auto-attribuer un rôle. La lecture passe par
 * `api.admin_profile()`, qui ne rend que le profil de l'appelant. Ce rôle sert
 * à afficher et à guider l'interface ; chaque écriture future le revérifiera
 * en base — l'interface n'est pas une barrière de sécurité (§14.2).
 */

export const ADMIN_ROLE_LABELS: Record<string, string> = {
  viewer_admin: 'consultation',
  content_admin: 'contenus officiels',
  data_admin: 'correction des données',
  super_admin: 'super administrateur',
};

export interface AdminProfile {
  role: string;
  status: 'invited' | 'active' | 'suspended';
  displayName: string;
  mfaRequired: boolean;
}

interface ProfileRow {
  role: string;
  status: string;
  display_name: string;
  mfa_required: boolean;
}

/**
 * Le client doit porter la session de l'appelant : celui de
 * `createPublicServerClient`, jamais le client public sans cookie.
 */
export async function fetchAdminProfile(supabase: SessionClient): Promise<AdminProfile | null> {
  const { data, error } = await supabase.rpc('admin_profile');

  if (error !== null) {
    console.error('[admin] lecture du profil impossible', {
      code: error.code,
      message: error.message,
    });
    return null;
  }

  const rows = (data ?? []) as ProfileRow[];
  const first = rows[0];
  if (first === undefined) return null;

  return {
    role: first.role,
    status: first.status as AdminProfile['status'],
    displayName: first.display_name,
    mfaRequired: first.mfa_required,
  };
}
