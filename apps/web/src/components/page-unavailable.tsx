import Link from 'next/link';
import type { ReactNode } from 'react';

/**
 * Une page entière quand la base n'a pas répondu à sa lecture principale.
 *
 * Ni 404 ni page d'erreur : un 404 ferait périmer une URL qui existe, et une
 * page d'erreur générique ne dirait pas que l'objet n'est pas en cause.
 * L'heure est écrite parce que ces pages sont servies en régénération
 * incrémentale : ce rendu peut être resservi quelques minutes, et doit dire
 * de quand il date. Même patron pour la fiche, la relecture, la commune et
 * le territoire (audit du 15 septembre 2026).
 */
export function PageUnavailable({
  eyebrow,
  title,
  children,
}: {
  /** Le fil d'Ariane réduit : « MPF-… / fiche indisponible », « 06004 / commune indisponible ». */
  eyebrow: string;
  title: string;
  /** Ce que la page ne peut pas affirmer, en une phrase. */
  children: ReactNode;
}) {
  const at = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Europe/Paris',
  }).format(new Date());

  return (
    <article className="shell max-w-[68ch] py-12">
      <p className="eyebrow mb-3">{eyebrow}</p>
      <h1 className="text-display max-w-[19ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        {title}
      </h1>
      <p className="text-lead text-(--text-2) mt-4">
        La base n’a pas répondu au moment d’établir cette page, le {at}. {children}
      </p>
      <p className="text-(--text-2) mt-4">
        Rechargez la page dans quelques instants. L’
        <Link href="/statut" className="underline underline-offset-4">
          état des données
        </Link>{' '}
        indique ce qui répond.
      </p>
    </article>
  );
}
