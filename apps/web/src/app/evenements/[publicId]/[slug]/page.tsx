import { redirect } from 'next/navigation';

import { eventPath, lookupEvent } from '@/lib/data/events';

import EventPage, { generateMetadata as eventMetadata } from '../page';

/**
 * URL avec slug éditorial — cahier FR-042 et FR-060 :
 * `/evenements/[publicId]/[slug?]`.
 *
 * Le slug est décoratif et **facultatif** : l'identifiant public suffit
 * toujours, et l'URL nue reste servie quoi qu'il arrive — c'est elle qui
 * porte la permanence (FR-042), le slug ne fait que s'y ajouter. Un segment
 * qui ne correspond pas au slug éditorial courant redirige vers la forme
 * canonique : en **307**, pas en 308 — un slug est éditorial, donc
 * modifiable, et une redirection permanente gravée dans les caches
 * survivrait à sa correction. Seules les fusions d'identifiants méritent le
 * définitif (§13.10).
 */

// Même valeur que la fiche nue — littérale, la configuration de segment doit
// être statiquement analysable.
export const revalidate = 120;

export const generateMetadata = eventMetadata;

export default async function SluggedEventPage({
  params,
}: {
  params: Promise<{ publicId: string; slug: string }>;
}) {
  const { publicId: rawPublicId, slug } = await params;
  const publicId = rawPublicId.toUpperCase();

  const lookup = await lookupEvent(publicId);

  // Le slug ne se vérifie que sur un événement lu. Tout le reste — base
  // muette, alias fusionné, identifiant inconnu ou hors périmètre — est
  // l'affaire de la fiche nue, qui sait le dire ; ce segment ne fait que
  // décorer son URL.
  if (
    lookup.readable &&
    lookup.value.kind === 'event' &&
    slug !== lookup.value.event.editorialSlug
  ) {
    redirect(eventPath(lookup.value.event));
  }

  return <EventPage params={Promise.resolve({ publicId })} />;
}
