import Link from 'next/link';

/**
 * La fiche — ou sa relecture — quand la base n'a pas répondu.
 *
 * Ni 404 ni page d'erreur : un 404 ferait périmer une URL qui existe
 * (§13.10), et une page d'erreur générique ne dirait pas que l'événement
 * n'est pas en cause. L'heure est écrite parce que la fiche est servie en
 * régénération incrémentale : ce rendu peut être resservi deux minutes, et
 * doit dire de quand il date.
 */
export function EventUnavailable({
  publicId,
  what = 'fiche',
}: {
  publicId: string;
  what?: 'fiche' | 'relecture';
}) {
  const at = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Europe/Paris',
  }).format(new Date());

  return (
    <article className="shell max-w-[68ch] py-12">
      <p className="eyebrow mb-3">
        {publicId} / {what} indisponible
      </p>
      <h1 className="text-display max-w-[19ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        {what === 'fiche' ? 'Fiche' : 'Relecture'} indisponible pour le moment
      </h1>
      <p className="text-lead text-(--text-2) mt-4">
        La base n’a pas répondu au moment d’établir cette page, le {at}. Cela ne dit rien de
        l’événement : il n’est ni introuvable ni retiré — il n’a pas pu être lu.
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
