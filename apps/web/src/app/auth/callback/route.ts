import { NextResponse, type NextRequest } from 'next/server';

import { createPublicServerClient } from '@/lib/supabase/server';

/**
 * GET /auth/callback — atterrissage du lien magique. Cahier §14.4.
 *
 * Deux formes de lien sont acceptées : le flux PKCE (`?code=`), produit par
 * défaut, et le flux `?token_hash=` qu'un gabarit d'e-mail personnalisé peut
 * émettre — ce dernier a l'avantage de fonctionner depuis un autre navigateur
 * que celui qui a demandé le lien. Dans les deux cas la session est posée en
 * cookie côté serveur, puis l'utilisateur est renvoyé vers l'administration.
 *
 * Aucun jeton n'est journalisé : un lien de connexion dans un journal est une
 * session volable (§14.3).
 */
export async function GET(request: NextRequest): Promise<Response> {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get('code');
  const tokenHash = searchParams.get('token_hash');

  const supabase = await createPublicServerClient();
  let succeeded = false;

  if (code !== null) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    succeeded = error === null;
  } else if (tokenHash !== null) {
    const { error } = await supabase.auth.verifyOtp({ type: 'email', token_hash: tokenHash });
    succeeded = error === null;
  }

  const destination = request.nextUrl.clone();
  destination.search = '';
  destination.pathname = succeeded ? '/admin' : '/admin/connexion';
  if (!succeeded) {
    // Cause volontairement générique : un lien peut être expiré, déjà employé
    // ou forgé, et la distinction n'aide que l'attaquant.
    destination.searchParams.set('erreur', 'lien');
  }

  return NextResponse.redirect(destination);
}
