import { inseeCodeSchema } from '@mapfeux/contracts';
import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { MapView } from '@/components/map/map-view';
import { fetchMunicipality } from '@/lib/data/municipalities';

/**
 * Synthèse communale. Cahier §7.1 et FR-022.
 *
 * Les détections, le panache et la qualité de l'air arrivent avec les lots 3, 5
 * et 6. La page affiche aujourd'hui l'identité de la commune ; chaque bloc
 * ajouté devra porter sa provenance et sa fraîcheur (§2.4).
 */

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ insee: string }>;
}): Promise<Metadata> {
  const { insee } = await params;
  const parsed = inseeCodeSchema.safeParse(insee.toUpperCase());
  if (!parsed.success) return { title: 'Commune introuvable' };

  const municipality = await fetchMunicipality(parsed.data);
  if (municipality === null) return { title: 'Commune introuvable' };

  return {
    title: municipality.name,
    description: `Situation des détections thermiques et informations locales pour ${municipality.name} (${municipality.departmentCode}).`,
  };
}

export default async function MunicipalityPage({ params }: { params: Promise<{ insee: string }> }) {
  const { insee } = await params;

  const parsed = inseeCodeSchema.safeParse(insee.toUpperCase());
  if (!parsed.success) notFound();

  const municipality = await fetchMunicipality(parsed.data);
  if (municipality === null) notFound();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <nav aria-label="Fil d’Ariane" className="text-(--text-2) text-sm">
        <Link href="/" className="underline underline-offset-4">
          Accueil
        </Link>
        {municipality.departmentSlug !== null && (
          <>
            {' / '}
            <Link
              href={`/territoire/${municipality.departmentSlug}`}
              className="underline underline-offset-4"
            >
              {municipality.departmentName ?? municipality.departmentCode}
            </Link>
          </>
        )}
      </nav>

      <h1 className="mt-2 text-3xl font-semibold tracking-tight">{municipality.name}</h1>
      <p className="text-(--text-2) mt-1 text-sm">
        Code INSEE {municipality.insee}
        {municipality.postalCodes.length > 0 &&
          ` · code${municipality.postalCodes.length > 1 ? 's' : ''} postal${
            municipality.postalCodes.length > 1 ? 'aux' : ''
          } ${municipality.postalCodes.join(', ')}`}
        {municipality.areaKm2 !== null &&
          ` · ${municipality.areaKm2.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} km²`}
      </p>

      <div className="border-(--border-strong) mt-6 h-72 overflow-hidden rounded border">
        <MapView
          center={[municipality.centroid.longitude, municipality.centroid.latitude]}
          zoom={11}
          className="h-full w-full"
        />
      </div>
      <p className="text-(--text-2) mt-2 text-xs">{MAP_DISCLAIMER}</p>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">Détections récentes</h2>
        <p className="text-(--text-2) mt-2">
          Les détections thermiques satellitaires ne sont pas encore importées. Cette section
          restera vide jusqu’à la mise en service du flux NASA FIRMS.
        </p>
      </section>

      <p className="text-(--text-3) mt-10 text-xs">
        Limites communales issues d’ADMIN EXPRESS COG, version {municipality.sourceVersion}.
      </p>
    </div>
  );
}
