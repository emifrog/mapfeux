import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

import { publicEnv } from '@/lib/env';

/**
 * Rafraîchissement de session et garde d'accès de l'administration.
 *
 * Référence : cahier §14.4 ; convention `proxy.ts` de Next 16.
 *
 * Un Server Component ne peut pas écrire de cookie : sans ce proxy, un jeton
 * expiré ne serait jamais renouvelé et l'administrateur serait déconnecté au
 * bout d'une heure. Le proxy tourne **uniquement** sur `/admin` : les pages
 * publiques restent sans lecture de cookie, donc cachables (§21.2).
 *
 * La garde ici ne vérifie que l'existence d'une session — un aller-retour
 * réseau, pas deux. Le rôle et le statut du profil sont vérifiés par le layout
 * protégé, et revérifiés en base à chaque écriture : ce proxy est une commodité
 * de parcours, pas la barrière de sécurité (§14.2).
 */

type CookieToSet = { name: string; value: string; options?: CookieOptions };

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    publicEnv.NEXT_PUBLIC_SUPABASE_URL,
    publicEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet: CookieToSet[]) => {
          for (const { name, value } of cookiesToSet) {
            request.cookies.set(name, value);
          }
          response = NextResponse.next({ request });
          for (const { name, value, options } of cookiesToSet) {
            response.cookies.set({ name, value, ...options });
          }
        },
      },
    },
  );

  // `getUser` revalide le jeton auprès du serveur d'authentification — jamais
  // de confiance dans le seul contenu du cookie.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;
  const isLoginPage = pathname === '/admin/connexion';

  if (user === null && !isLoginPage) {
    return redirectPreservingCookies(request, response, '/admin/connexion');
  }
  if (user !== null && isLoginPage) {
    return redirectPreservingCookies(request, response, '/admin');
  }

  return response;
}

/**
 * Un jeton parfois rafraîchi pendant `getUser` vit dans `response` : une
 * redirection nue le perdrait, et la session expirerait quand même.
 */
function redirectPreservingCookies(
  request: NextRequest,
  response: NextResponse,
  destination: string,
): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = destination;
  url.search = '';

  const redirect = NextResponse.redirect(url);
  for (const cookie of response.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  return redirect;
}

export const config = {
  matcher: ['/admin/:path*'],
};
