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
    <div className="shell max-w-[880px] py-10">
      <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-2">
        <Link href="/" className="hover:text-(--text-2)">
          accueil
        </Link>
        {municipality.departmentSlug !== null && (
          <>
            <span aria-hidden="true" className="text-(--border-strong)">
              /
            </span>
            <Link
              href={`/territoire/${municipality.departmentSlug}`}
              className="hover:text-(--text-2)"
            >
              {municipality.departmentName ?? municipality.departmentCode}
            </Link>
          </>
        )}
        <span aria-hidden="true" className="text-(--border-strong)">
          /
        </span>
        <span>commune</span>
      </nav>

      <h1 className="text-display mt-3 max-w-[16ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        {municipality.name}
      </h1>

      {/* Identité administrative : des références, donc de la chasse fixe. */}
      <p className="text-small text-(--text-2) mono mt-3">
        INSEE {municipality.insee}
        {municipality.postalCodes.length > 0 && ` · CP ${municipality.postalCodes.join(', ')}`}
        {municipality.areaKm2 !== null &&
          ` · ${municipality.areaKm2.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} km²`}
      </p>

      <div
        className="mt-8 h-72 overflow-hidden rounded-lg border sm:h-80"
        style={{ borderColor: 'var(--border-strong)' }}
      >
        <MapView
          center={[municipality.centroid.longitude, municipality.centroid.latitude]}
          zoom={11}
          className="h-full w-full"
        />
      </div>
      <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">{MAP_DISCLAIMER}</p>

      <section className="mt-12" aria-labelledby="detections">
        <h2 id="detections" className="text-title font-bold tracking-tight">
          Détections sur cette commune
        </h2>
        {/*
          Cette section annonçait que « les détections ne sont pas encore
          importées ». C'était vrai jusqu'au 5 août 2026 ; l'ingestion tourne
          depuis, et la phrase est devenue une affirmation fausse sur une page
          publique — le contraire de ce que §2.4 demande.
          Le rattachement d'un événement à sa commune existe en base ; son
          affichage ici reste à écrire. D'ici là, la page dit ce qu'elle sait et
          renvoie où l'information se trouve.
        */}
        <p className="text-(--text-2) mt-3 max-w-[68ch]">
          Les détections thermiques sont importées et regroupées, mais leur affichage par commune
          n’est pas encore en service. En attendant, la{' '}
          <Link href="/carte" className="underline underline-offset-4">
            carte
          </Link>{' '}
          montre les événements de la zone, et l’
          <Link href="/statut" className="underline underline-offset-4">
            état des données
          </Link>{' '}
          indique depuis quand la donnée date.
        </p>
        <p className="text-small text-(--text-3) mt-3 max-w-[68ch]">
          L’absence d’événement affiché ici ne signifie pas qu’il ne s’en produit pas.
        </p>
      </section>

      <p className="text-micro text-(--text-3) mt-12 max-w-[68ch]">
        Limites communales issues d’ADMIN EXPRESS COG, version{' '}
        <span className="mono">{municipality.sourceVersion}</span>.
      </p>
    </div>
  );
}
