import { notFound, permanentRedirect, redirect } from 'next/navigation';

import { eventPath, fetchEvent, resolveEventAlias } from '@/lib/data/events';

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

  const event = await fetchEvent(publicId);
  if (event === null) {
    const canonical = await resolveEventAlias(publicId);
    if (canonical !== null && canonical !== publicId) {
      permanentRedirect(`/evenements/${canonical}`);
    }
    notFound();
  }

  if (slug !== event.editorialSlug) {
    redirect(eventPath(event));
  }

  return <EventPage params={Promise.resolve({ publicId })} />;
}
