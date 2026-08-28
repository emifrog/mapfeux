import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { MapView } from '@/components/map/map-view';
import { MunicipalitySearch } from '@/components/municipality-search';
import { fetchDepartmentMassifLevels, fetchDepartmentOfficialItems } from '@/lib/data/official';
import { fetchOfficialLinks, fetchTerritories, fetchTerritory } from '@/lib/data/territories';

/**
 * Vue territoriale. Cahier §7.1, FR-013.
 *
 * L'URL est partageable et porte à elle seule le territoire consulté : aucun
 * état de session n'est nécessaire pour retrouver la même vue.
 */

// La page porte désormais les publications captées, pas seulement la
// configuration : dix minutes suivent le rythme préfectoral sans coûter.
export const revalidate = 600;

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

  const [officialLinks, allTerritories, officialItems, massifLevels] = await Promise.all([
    fetchOfficialLinks(slug),
    fetchTerritories(),
    // Les citations sont départementales — la liste blanche l'est (ADR-026).
    territory.type === 'department'
      ? fetchDepartmentOfficialItems(territory.code)
      : Promise.resolve([]),
    territory.type === 'department'
      ? fetchDepartmentMassifLevels(territory.code)
      : Promise.resolve([]),
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
            <Link href={`/territoires/${parent.slug}`} className="hover:text-(--text-2)">
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

      {territory.type === 'department' && massifLevels.length > 0 && (
        <section className="mt-12" aria-labelledby="massifs">
          <h2 id="massifs" className="text-title font-bold tracking-tight">
            Accès aux massifs forestiers
          </h2>
          {/* ADR-026 : les niveaux et leurs libellés sont ceux du site
              interservices des préfectures, verbatim — MapFeux n'ajoute ni
              couleur d'alerte ni interprétation. */}
          <ul className="mt-4 space-y-2">
            {massifLevels.map((massif) => (
              <li key={`${massif.massifName}-${massif.validOn}`} className="max-w-[68ch]">
                <span className="font-semibold">{massif.massifName}</span>
                <span className="text-(--text-2)">
                  {' — '}
                  <time dateTime={massif.validOn} className="mono">
                    {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short' }).format(
                      new Date(massif.validOn),
                    )}
                  </time>
                  {' : '}
                  {massif.levelLabel ?? `niveau ${massif.level}`}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-small text-(--text-3) mt-4 max-w-[68ch]">
            Niveaux et libellés repris tels que publiés par les préfectures sur{' '}
            <a
              href={massifLevels[0]?.sourceUrl}
              className="underline underline-offset-4"
              rel="noopener noreferrer"
            >
              risque-prevention-incendie.fr
            </a>
            , mis à jour chaque jour vers 18 h. La capture est automatique : en cas de doute, la
            carte officielle fait foi.
          </p>
        </section>
      )}

      {territory.type === 'department' && (
        <section className="mt-12" aria-labelledby="publications">
          <h2 id="publications" className="text-title font-bold tracking-tight">
            Publications de la préfecture
          </h2>
          {/* FR-104 et ADR-026 : des citations attribuées et datées, jamais
              réécrites — rien ici n'est une estimation de MapFeux. */}
          {officialItems.length === 0 ? (
            <p className="text-small text-(--text-2) mt-4 max-w-[68ch]">
              Aucune publication captée pour ce département. Cela ne signifie pas qu’il n’en existe
              pas : consultez directement le site de la préfecture.
            </p>
          ) : (
            <>
              <ul className="mt-4 space-y-3">
                {officialItems.map((item) => (
                  <li key={item.url}>
                    <a
                      href={item.url}
                      className="underline underline-offset-4"
                      rel="noopener noreferrer"
                    >
                      {item.title}
                    </a>
                    <span className="eyebrow mt-0.5 block">
                      {item.organisation}
                      {item.publishedOn !== null && (
                        <>
                          {' · publié le '}
                          <time dateTime={item.publishedOn} className="mono">
                            {new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short' }).format(
                              new Date(item.publishedOn),
                            )}
                          </time>
                        </>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-small text-(--text-3) mt-4 max-w-[68ch]">
                Titres repris tels que publiés par la préfecture, sans reformulation ; chaque lien
                mène à la publication d’origine. La capture est automatique : une publication
                récente peut ne pas encore apparaître.
              </p>
            </>
          )}
        </section>
      )}

      {children.length > 0 && (
        <section className="mt-12" aria-labelledby="rattaches">
          <h2 id="rattaches" className="text-title font-bold tracking-tight">
            Territoires rattachés
          </h2>
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
            {children.map((child) => (
              <li key={child.slug}>
                <Link href={`/territoires/${child.slug}`} className="underline underline-offset-4">
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
