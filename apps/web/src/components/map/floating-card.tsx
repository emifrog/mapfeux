/**
 * Carte flottante posée sur la carte géographique.
 *
 * Référence : cahier §6.5.
 *
 * Depuis le 11 septembre 2026, `/carte` est une coque d'application : la
 * carte occupe l'écran, et tout le reste flotte au-dessus. Ces cartons en
 * sont le matériau commun — même fond translucide, même flou, même
 * bordure. Trois recopies de ces styles auraient divergé à la première
 * retouche de palette ; et ils ne sont pas de simples classes, le
 * `color-mix` et le flou d'arrière-plan n'ayant pas d'utilitaire.
 *
 * Le composant n'est pas client : il sert au serveur — l'identité de la
 * page, la liste des événements — comme aux panneaux interactifs.
 *
 * ## Translucide, mais pas transparent
 *
 * 92 % d'opacité : la carte se devine derrière le carton, ce qui dit
 * qu'il flotte, sans qu'aucun texte n'ait à se lire par-dessus des
 * toponymes. Un carton franchement transparent serait joli et illisible.
 */

export function FloatingCard({
  children,
  className = '',
  labelledBy,
  as: Tag = 'section',
}: {
  children: React.ReactNode;
  className?: string;
  labelledBy?: string;
  as?: 'section' | 'div' | 'aside';
}) {
  return (
    <Tag
      {...(labelledBy === undefined ? {} : { 'aria-labelledby': labelledBy })}
      className={`rounded-xl border p-3 shadow-lg ${className}`}
      style={{
        background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
        borderColor: 'var(--border)',
        backdropFilter: 'blur(6px)',
      }}
    >
      {children}
    </Tag>
  );
}
