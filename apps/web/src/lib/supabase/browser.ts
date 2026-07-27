import { createBrowserClient } from '@supabase/ssr';

import { publicEnv } from '@/lib/env';

/**
 * Client navigateur, limité au schéma public `api` et à la clé publiable.
 * Utilisé par les composants interactifs (carte, recherche) et, plus tard, par
 * l'authentification administrateur. Cahier §14.1.
 */
export function createPublicBrowserClient() {
  return createBrowserClient(
    publicEnv.NEXT_PUBLIC_SUPABASE_URL,
    publicEnv.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    { db: { schema: 'api' } },
  );
}
