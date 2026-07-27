import { z } from 'zod';

/**
 * Validation de l'environnement au démarrage.
 *
 * Référence : cahier annexe C et §14.3.
 *
 * `SUPABASE_SECRET_KEY` n'est lue que par `getServerEnv`, jamais exportée vers
 * un composant client : une clé privilégiée dans le bundle JavaScript est un
 * critère de blocage du lancement (§28.1).
 *
 * Le cahier annexe C nommait cette variable `SUPABASE_SERVICE_ROLE_KEY`, du nom
 * de l'ancienne clé JWT. Supabase l'a remplacée par une « secret key »
 * `sb_secret_…` ; le nom suit la terminologie du fournisseur pour éviter qu'on
 * cherche dans le tableau de bord une clé qui ne s'y appelle plus ainsi.
 */

const publicEnvSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z.string().min(20),
});

const serverEnvSchema = z.object({
  SUPABASE_SECRET_KEY: z.string().min(20).optional(),
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
    SUPABASE_SECRET_KEY: process.env.SUPABASE_SECRET_KEY,
    PUBLIC_APP_URL: process.env.PUBLIC_APP_URL,
    API_CACHE_SECRET: process.env.API_CACHE_SECRET,
  });
}
