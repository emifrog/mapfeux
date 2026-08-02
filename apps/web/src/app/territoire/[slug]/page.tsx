import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { MapView } from '@/components/map/map-view';
import { MunicipalitySearch } from '@/components/municipality-search';
import { fetchOfficialLinks, fetchTerritories, fetchTerritory } from '@/lib/data/territories';

/**
 * Vue territoriale. Cahier §7.1, FR-013.
 *
 * L'URL est partageable et porte à elle seule le territoire consulté : aucun
 * état de session n'est nécessaire pour retrouver la même vue.
 */

// La configuration territoriale est administrée à la main et change rarement.
export const revalidate = 3600;

const LINK_CATEGORY_LABELS: Record<string, string> = {
  prefecture: 'Préfecture',
  sdis: 'Service d’incendie et de secours',
  massif_access: 'Accès aux massifs',
  vigilance: 'Vigilance',
  air_quality: 'Qualité de l’air',
  other: 'Autre',
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const territory = await fetchTerritory(slug);

  if (territory === null) {
    return { title: 'Territoire introuvable' };
  }

  return {
    title: territory.name,
    description: `Détections thermiques satellitaires et informations officielles pour ${territory.name}.`,
  };
}

export default async function TerritoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  const territory = await fetchTerritory(slug);
  if (territory === null) notFound();

  const [officialLinks, allTerritories] = await Promise.all([
    fetchOfficialLinks(slug),
    fetchTerritories(),
  ]);

  const children = allTerritories.filter((t) => t.parentSlug === territory.slug);
  const parent =
    territory.parentSlug === null
      ? null
      : (allTerritories.find((t) => t.slug === territory.parentSlug) ?? null);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <nav aria-label="Fil d’Ariane" className="text-sm text-[--text-2]">
        <Link href="/" className="underline underline-offset-4">
          Accueil
        </Link>
        {parent !== null && (
          <>
            {' / '}
            <Link href={`/territoire/${parent.slug}`} className="underline underline-offset-4">
              {parent.name}
            </Link>
          </>
        )}
      </nav>

      <h1 className="mt-2 text-3xl font-semibold tracking-tight">{territory.name}</h1>
      <p className="mt-1 text-sm text-[--text-2]">
        Code {territory.code} · fuseau {territory.timezone}
        {territory.status === 'pilot' && ' · territoire pilote'}
      </p>

      <div className="mt-6 h-80 overflow-hidden rounded border border-[--border-strong]">
        <MapView
          center={[territory.center.longitude, territory.center.latitude]}
          zoom={territory.defaultZoom}
          className="h-full w-full"
        />
      </div>
      <p className="mt-2 text-xs text-[--text-2]">{MAP_DISCLAIMER}</p>

      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <section>
          <h2 className="text-xl font-semibold">Rechercher une commune</h2>
          <div className="mt-3">
            <MunicipalitySearch />
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold">Informations officielles</h2>
          {officialLinks.length === 0 ? (
            <p className="mt-3 text-sm text-[--text-2]">
              Aucun lien officiel n’est encore renseigné pour ce territoire.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {officialLinks.map((link) => (
                <li key={link.url}>
                  <a
                    href={link.url}
                    className="underline underline-offset-4"
                    rel="noopener noreferrer"
                  >
                    {link.title}
                  </a>
                  <span className="block text-xs text-[--text-2]">
                    {LINK_CATEGORY_LABELS[link.category] ?? link.category} · {link.organisation}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {children.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold">Territoires rattachés</h2>
          <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
            {children.map((child) => (
              <li key={child.slug}>
                <Link href={`/territoire/${child.slug}`} className="underline underline-offset-4">
                  {child.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
