import { z } from 'zod';

/**
 * Validation de l'environnement au démarrage.
 *
 * Référence : cahier annexe C et §14.3.
 *
 * `SUPABASE_SERVICE_ROLE_KEY` n'est lu que par `serverEnv`, jamais exporté vers
 * un composant client : une clé de service dans le bundle JavaScript est un
 * critère de blocage du lancement (§28.1).
 */

const publicEnvSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z.string().min(20),
});

const serverEnvSchema = z.object({
  SUPABASE_SERVICE_ROLE_KEY: z.string().min(20).optional(),
  PUBLIC_APP_URL: z.string().url().default('http://localhost:3000'),
  API_CACHE_SECRET: z.string().optional(),
});

/** Variables disponibles côté navigateur. Toujours préfixées NEXT_PUBLIC_. */
export const publicEnv = publicEnvSchema.parse({
  NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
});

/**
 * Variables strictement serveur. L'accès depuis un composant client déclenche
 * une erreur de construction Next, ce qui est le comportement recherché.
 */
export function getServerEnv() {
  return serverEnvSchema.parse({
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    PUBLIC_APP_URL: process.env.PUBLIC_APP_URL,
    API_CACHE_SECRET: process.env.API_CACHE_SECRET,
  });
}
