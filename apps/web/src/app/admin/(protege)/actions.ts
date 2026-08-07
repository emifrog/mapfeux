'use server';

import { redirect } from 'next/navigation';

import { createPublicServerClient } from '@/lib/supabase/server';

/** Déconnexion : révoque la session côté serveur puis efface les cookies. */
export async function seDeconnecter(): Promise<void> {
  const supabase = await createPublicServerClient();
  await supabase.auth.signOut();
  redirect('/admin/connexion');
}
