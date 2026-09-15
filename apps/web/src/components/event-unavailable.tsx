import { PageUnavailable } from '@/components/page-unavailable';

/**
 * La fiche — ou sa relecture — quand la base n'a pas répondu. Voir
 * `PageUnavailable` pour le patron ; ici, ce que la page ne dit pas de
 * l'événement.
 */
export function EventUnavailable({
  publicId,
  what = 'fiche',
}: {
  publicId: string;
  what?: 'fiche' | 'relecture';
}) {
  return (
    <PageUnavailable
      eyebrow={`${publicId} / ${what} indisponible`}
      title={`${what === 'fiche' ? 'Fiche' : 'Relecture'} indisponible pour le moment`}
    >
      Cela ne dit rien de l’événement : il n’est ni introuvable ni retiré — il n’a pas pu être lu.
    </PageUnavailable>
  );
}
