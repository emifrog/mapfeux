'use server';

import { redirect } from 'next/navigation';
import { z } from 'zod';

import { getServerEnv } from '@/lib/env';
import { createPublicServerClient } from '@/lib/supabase/server';

/**
 * Envoi du lien magique. Cahier §14.4.
 *
 * `shouldCreateUser: false` : cette page ne crée jamais de compte. Un
 * administrateur entre par `scripts/grant-admin.py`, qui crée l'utilisateur et
 * son profil — la page de connexion n'est pas une porte d'inscription.
 *
 * La confirmation est identique que le compte existe ou non : la page ne doit
 * pas servir d'oracle à l'énumération d'adresses (§22.4).
 */

const emailSchema = z.string().trim().toLowerCase().email();

export async function envoyerLienDeConnexion(formData: FormData): Promise<void> {
  const parsed = emailSchema.safeParse(formData.get('email'));
  if (!parsed.success) {
    redirect('/admin/connexion?erreur=email');
  }

  const supabase = await createPublicServerClient();
  await supabase.auth.signInWithOtp({
    email: parsed.data,
    options: {
      emailRedirectTo: `${getServerEnv().PUBLIC_APP_URL}/auth/callback`,
      shouldCreateUser: false,
    },
  });

  redirect('/admin/connexion?envoye=1');
}
