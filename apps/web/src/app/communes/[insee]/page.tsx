import { inseeCodeSchema } from '@mapfeux/contracts';
import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { EventList } from '@/components/event-list';
import { MapView } from '@/components/map/map-view';
import { MunicipalityAir } from '@/components/municipality-air';
import { fetchEventsNearMunicipality } from '@/lib/data/events';
import { fetchMunicipality } from '@/lib/data/municipalities';

/** Les événements rattachés à la commune sur les trente derniers jours. */
const EVENTS_WINDOW_DAYS = 30;

/**
 * Synthèse communale. Cahier §7.1 et FR-022.
 *
 * La qualité de l'air modélisée est en service (§19.2) ; les détections et
 * le panache arrivent avec leurs lots. Chaque bloc porte sa provenance et sa
 * fraîcheur (§2.4).
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

  const now = new Date();
  const since = new Date(now.getTime() - EVENTS_WINDOW_DAYS * 24 * 3_600_000);
  const events = await fetchEventsNearMunicipality(municipality, { since });

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
              href={`/territoires/${municipality.departmentSlug}`}
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
          events={events.map((event) => ({
            publicId: event.publicId,
            freshnessStatus: event.freshnessStatus,
            lastDetectedAt: event.lastDetectedAt.toISOString(),
            confidence: event.confidenceLevel,
            detectionCount: event.detectionCount,
            location: event.location,
            nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
          }))}
        />
      </div>
      <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">{MAP_DISCLAIMER}</p>

      <section className="mt-12" aria-labelledby="detections">
        <h2 id="detections" className="text-title font-bold tracking-tight">
          Détections sur cette commune
        </h2>
        {/*
          Les événements dont cette commune est la plus proche, sur trente
          jours, dans les mots et les formes de la liste de la carte (§8.6).
          Cette section a longtemps dit que « l'affichage par commune n'est
          pas encore en service » — vrai du 5 août au 15 septembre 2026,
          et une phrase d'attente de plus à surveiller (plan §15). Le
          rattachement existait en base depuis l'ingestion ; il est lu ici.

          « Rattaché », pas « sur » : un événement reçoit la commune
          française la plus proche, sans limite de distance. La lecture se
          borne à une vingtaine de kilomètres du centroïde, et la phrase le
          dit — un site étranger rattaché à une commune frontalière n'est
          pas « sur cette commune » au sens où un lecteur l'entend.
        */}
        <p className="text-small text-(--text-2) mt-2 max-w-[68ch]">
          Événements dont cette commune est la plus proche, sur les {EVENTS_WINDOW_DAYS} derniers
          jours. Relevé à{' '}
          <time dateTime={now.toISOString()} className="mono">
            {new Intl.DateTimeFormat('fr-FR', {
              dateStyle: 'short',
              timeStyle: 'short',
              timeZone: 'Europe/Paris',
            }).format(now)}
          </time>
          .
        </p>
        <div className="mt-4 max-w-[68ch]">
          <EventList events={events} now={now} />
        </div>
        {municipality.departmentSlug === null && (
          <p className="text-small text-(--text-2) mt-4 max-w-[68ch]">
            Ce département n’est pas encore un territoire ouvert : sa page dédiée et ses liens
            officiels vérifiés restent à venir. La{' '}
            <Link href="/carte" className="underline underline-offset-4">
              carte
            </Link>{' '}
            montre les événements de la zone, et l’
            <Link href="/statut" className="underline underline-offset-4">
              état des données
            </Link>{' '}
            indique depuis quand la donnée date.
          </p>
        )}
        <p className="text-small text-(--text-3) mt-3 max-w-[68ch]">
          L’absence d’événement affiché ici ne signifie pas qu’il ne s’en produit pas.
        </p>
      </section>

      <MunicipalityAir
        longitude={municipality.centroid.longitude}
        latitude={municipality.centroid.latitude}
      />

      <p className="text-micro text-(--text-3) mt-12 max-w-[68ch]">
        Limites communales issues d’ADMIN EXPRESS COG, version{' '}
        <span className="mono">{municipality.sourceVersion}</span>.
      </p>
    </div>
  );
}
