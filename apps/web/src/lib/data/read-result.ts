/**
 * Résultat de lecture explicite.
 *
 * « Rien » et « je n'ai pas pu lire » sont deux réponses différentes, qu'un
 * tableau vide ou un `null` confondent. Jusqu'au 15 septembre 2026, une base
 * qui ne répondait pas faisait afficher zéro événement à l'accueil, répondre
 * 200 au catalogue — liste vide, mise en cache une minute par le CDN — et
 * 404 à la fiche : le lecteur n'avait aucun moyen de distinguer « aucune
 * observation » de « impossible de lire les observations », ce que le cahier
 * proscrit (§5.13, §21.5). Un audit externe l'a reproduit ce jour-là.
 *
 * Même patron que `SourceStatusResult` (`lib/sources.ts`), généralisé aux
 * événements : la lecture dit si elle a lu, l'appelant ne devine pas.
 *
 * - `readable: true` — la base a répondu ; `value` est ce qu'elle a dit,
 *   y compris « rien » (`[]`, `null`).
 * - `readable: false` — la base n'a pas répondu ; il n'y a **pas** de
 *   valeur, et l'appelant doit le dire plutôt que de montrer une absence.
 */
export type ReadResult<T> =
  { readonly readable: true; readonly value: T } | { readonly readable: false };

export function readable<T>(value: T): ReadResult<T> {
  return { readable: true, value };
}

const UNREADABLE: { readonly readable: false } = { readable: false };

export function unreadable<T>(): ReadResult<T> {
  return UNREADABLE;
}

/**
 * La valeur lue, ou un repli **quand l'appelant annonce la panne par
 * ailleurs**. Ne pas s'en servir pour taire une lecture manquée : c'est
 * exactement le raccourci que ce type existe pour interdire.
 */
export function valueOr<T>(result: ReadResult<T>, fallback: T): T {
  return result.readable ? result.value : fallback;
}
