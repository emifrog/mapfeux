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
    <div className="shell py-10">
      <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-2">
        <Link href="/" className="hover:text-(--text-2)">
          accueil
        </Link>
        {parent !== null && (
          <>
            <span aria-hidden="true" className="text-(--border-strong)">
              /
            </span>
            <Link href={`/territoire/${parent.slug}`} className="hover:text-(--text-2)">
              {parent.name}
            </Link>
          </>
        )}
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>territoire</span>
      </nav>

      <h1 className="text-display mt-3 max-w-[16ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        {territory.name}
      </h1>

      <p className="text-small text-(--text-2) mono mt-3">
        {territory.code} · {territory.timezone}
        {territory.status === 'pilot' && ' · territoire pilote'}
      </p>

      {/* La carte prend la largeur de la coque, la lecture reste en colonne —
          même arbitrage que sur /carte. */}
      <div
        className="lg:h-104 mt-8 h-80 overflow-hidden rounded-lg border"
        style={{ borderColor: 'var(--border-strong)' }}
      >
        <MapView
          center={[territory.center.longitude, territory.center.latitude]}
          zoom={territory.defaultZoom}
          className="h-full w-full"
        />
      </div>
      <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">{MAP_DISCLAIMER}</p>

      <div className="mt-12 grid gap-10 md:grid-cols-2">
        <section aria-labelledby="recherche">
          <h2 id="recherche" className="text-title font-bold tracking-tight">
            Rechercher une commune
          </h2>
          <div className="mt-4 max-w-md">
            <MunicipalitySearch />
          </div>
        </section>

        <section aria-labelledby="officiel">
          <h2 id="officiel" className="text-title font-bold tracking-tight">
            Informations officielles
          </h2>
          {officialLinks.length === 0 ? (
            // L'absence est énoncée, jamais laissée à l'interprétation : un
            // blanc se lirait comme « rien à signaler » (§2.4).
            <p className="text-small text-(--text-2) mt-4 max-w-[68ch]">
              Aucun lien officiel n’est encore renseigné pour ce territoire. Cela ne signifie pas
              qu’il n’en existe pas.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {officialLinks.map((link) => (
                <li key={link.url}>
                  <a
                    href={link.url}
                    className="underline underline-offset-4"
                    rel="noopener noreferrer"
                  >
                    {link.title}
                  </a>
                  <span className="eyebrow mt-0.5 block">
                    {LINK_CATEGORY_LABELS[link.category] ?? link.category} · {link.organisation}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {children.length > 0 && (
        <section className="mt-12" aria-labelledby="rattaches">
          <h2 id="rattaches" className="text-title font-bold tracking-tight">
            Territoires rattachés
          </h2>
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
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
