import 'server-only';

import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { createClient } from '@supabase/supabase-js';
import { cookies } from 'next/headers';

import { getServerEnv, publicEnv } from '@/lib/env';

/**
 * Clients Supabase côté serveur.
 *
 * Référence : cahier §12.1 et §14.1.
 *
 * Seul le schéma `api` est interrogé : les schémas internes ne sont pas exposés
 * par la Data API, et une requête vers `fire.detections` échouerait de toute
 * façon faute de grants. C'est volontaire — la surface publique est un contrat,
 * pas une conséquence des politiques RLS.
 */
const PUBLIC_SCHEMA = 'api';

/**
 * Client de lecture publique, avec la clé publiable et le rôle `anon`.
 * Les cookies d'authentification sont transmis afin qu'un administrateur
 * connecté conserve sa session, sans lui accorder de droits supplémentaires.
 */
export async function createPublicServerClient() {
  const cookieStore = await cookies();

  return createServerClient(
    publicEnv.NEXT_PUBLIC_SUPABASE_URL,
    publicEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    {
      db: { schema: PUBLIC_SCHEMA },
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet: { name: string; value: string; options?: CookieOptions }[]) => {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set({ name, value, ...options });
            }
          } catch {
            // Appel depuis un Server Component : les cookies y sont en lecture
            // seule. Le rafraîchissement de session est alors assuré par
            // `proxy.ts`. Ignorer ici est le comportement documenté.
          }
        },
      },
    },
  );
}

/**
 * Client privilégié réservé aux traitements serveur : imports déclenchés depuis
 * l'administration, écritures contrôlées et lecture des schémas internes.
 *
 * Ne jamais l'exposer à un composant client, ni l'utiliser pour rendre une page
 * publique : il contourne l'intégralité des politiques RLS. §14.3
 */
export function createServiceRoleClient() {
  const env = getServerEnv();

  if (env.SUPABASE_SERVICE_ROLE_KEY === undefined) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY absente : les opérations privilégiées sont indisponibles.',
    );
  }

  return createClient(publicEnv.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
