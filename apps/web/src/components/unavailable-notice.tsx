import type { ReactNode } from 'react';

/**
 * Bandeau d'indisponibilité : la page ne sait pas, et le dit.
 *
 * Une lecture manquée n'est pas une absence — « 0 événement » sur une panne
 * est la fausse assurance que le cahier proscrit (§5.13, §21.5). Le bandeau
 * remplace le chiffre ou la liste qu'il n'a pas pu établir, dans la couleur
 * « dégradé » de /statut — jamais l'orange, qui appartient à l'observation
 * thermique (§9.5). `role="status"` : la lecture d'écran l'annonce sans
 * l'imposer.
 */
export function UnavailableNotice({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={`text-small rounded-md border-l-[3px] px-4 py-3 ${className}`.trim()}
      style={{
        background: 'var(--color-degraded-wash)',
        borderColor: 'var(--color-degraded)',
        color: 'var(--color-degraded)',
      }}
    >
      {children}
    </div>
  );
}
