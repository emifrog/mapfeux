import type { Metadata } from 'next';
import Link from 'next/link';

/**
 * Tableau de bord d'administration — squelette. Cahier §7.2 et §20.1.
 *
 * L'authentification est le livrable de ce jalon ; les fonctions
 * d'administration — supervision des sources, correction, fusion, messages
 * officiels — arrivent avec J5. Cette page dit ce qui existe et ce qui
 * n'existe pas encore, plutôt que d'exposer des boutons morts.
 */

export const metadata: Metadata = {
  title: 'Administration',
};

export default function AdminHomePage() {
  return (
    <div className="max-w-[68ch] py-10">
      <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Administration
      </h1>

      <p className="text-(--text-2) mt-4 max-w-[56ch]">
        L’authentification est en place ; les outils d’administration — supervision des sources,
        correction et fusion d’événements, messages officiels — arrivent avec le jalon J5. En
        attendant, l’état des données reste la vue d’exploitation de référence.
      </p>

      <ul className="mt-8 space-y-2">
        <li>
          <Link href="/statut" className="underline underline-offset-4">
            État des données
          </Link>{' '}
          <span className="text-small text-(--text-2)">— fraîcheur des sources et incidents</span>
        </li>
        <li>
          <Link href="/carte" className="underline underline-offset-4">
            Carte publique
          </Link>{' '}
          <span className="text-small text-(--text-2)">— ce que voient les visiteurs</span>
        </li>
      </ul>
    </div>
  );
}
