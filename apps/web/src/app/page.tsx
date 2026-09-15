import { isHealthy, isInService, MAP_DISCLAIMER } from '@mapfeux/domain';
import { DEFAULT_VIEW } from '@mapfeux/map-style';
import Link from 'next/link';

import { MapView } from '@/components/map/map-view';
import { MunicipalitySearch } from '@/components/municipality-search';
import { NearMe } from '@/components/near-me';
import { UnavailableNotice } from '@/components/unavailable-notice';
import { fetchDepartmentAggregates } from '@/lib/data/events';
import { fetchTerritories } from '@/lib/data/territories';
import { fetchSourceStatus } from '@/lib/sources';

/**
 * Accueil. Cahier §8.1.
 *
 * L'utilisateur doit comprendre en moins de cinq secondes ce que le service
 * montre, sur quel territoire, et son caractère non officiel. La recherche est
 * placée avant tout le reste : c'est la seule action que quelqu'un vient
 * réellement faire ici.
 *
 * ## La carte en tête — 13 septembre 2026
 *
 * L'accueil s'ouvrait sur de la prose, et « ouvrir la carte » était un lien
 * texte. Les deux références regardées ce jour-là s'ouvrent sur une carte
 * et trois grands chiffres. La carte nationale est donc ici, **vivante** :
 * les lavis départementaux des sept derniers jours se chargent d'eux-mêmes,
 * au zoom pour lequel ils ont été dessinés (§21.3). Elle ne se manipule pas —
 * elle mène à `/carte`. Les chiffres sont ceux de la base à l'instant du
 * rendu, pas des promesses : événements observés, départements concernés,
 * sources qui répondent. Et quand la base n'a pas répondu, ils ne sont pas
 * des zéros : un tiret, et un bandeau qui le dit — jusqu'au 15 septembre
 * 2026, une panne de lecture affichait « 0 événement » (constat d'audit).
 *
 * Ce qui n'a pas bougé : le titre — une formulation publique, qui passe par
 * une validation métier avant d'être modifiée —, l'avertissement du §2.4 et
 * son filet orange, seul domaine auquel cette couleur appartient.
 */

// Des chiffres vivants, pas une brochure : cinq minutes, comme l'API.
export const revalidate = 300;

const HOURS_24_MS = 24 * 3_600_000;
const DAYS_7_MS = 7 * HOURS_24_MS;

const COMPACT = new Intl.NumberFormat('fr-FR');

export default async function HomePage() {
  const now = new Date();
  const [territories, last24h, last7d, status] = await Promise.all([
    fetchTerritories(),
    fetchDepartmentAggregates(new Date(now.getTime() - HOURS_24_MS)),
    fetchDepartmentAggregates(new Date(now.getTime() - DAYS_7_MS)),
    fetchSourceStatus(),
  ]);
  const departments = territories.filter((territory) => territory.type === 'department');

  // Une somme sur des lignes non lues vaudrait zéro : on ne somme que ce
  // qui a été lu, et un chiffre non établi s'écrit « — ».
  const events24h = last24h.readable
    ? last24h.value.reduce((sum, row) => sum + row.events, 0)
    : null;
  const events7d = last7d.readable ? last7d.value.reduce((sum, row) => sum + row.events, 0) : null;
  const departmentsTouched = last7d.readable ? last7d.value.length : null;
  const inService = status.sources.filter((source) => isInService(source.freshness));
  const healthy = inService.filter((source) => isHealthy(source.freshness)).length;
  const anyUnreadable = !last24h.readable || !last7d.readable || !status.readable;

  const NOT_READ = 'non consultable à cet instant';
  const figures = [
    {
      value: events24h === null ? '—' : COMPACT.format(events24h),
      label: 'événements observés',
      detail: events24h === null ? NOT_READ : 'dernières 24 heures, France entière',
    },
    {
      value: departmentsTouched === null ? '—' : COMPACT.format(departmentsTouched),
      label: 'départements concernés',
      detail: events7d === null ? NOT_READ : `${COMPACT.format(events7d)} événements sur 7 jours`,
    },
    {
      value: status.readable ? `${healthy}/${inService.length}` : '—',
      label: 'sources à jour',
      detail: status.readable ? 'état des données en direct' : NOT_READ,
      href: '/statut',
    },
  ];

  return (
    <div className="shell py-10">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr] lg:items-center lg:gap-12">
        <div>
          <p className="eyebrow mb-3">observation satellitaire · France</p>

          <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
            Où sont les détections thermiques en France
          </h1>

          <p className="text-lead text-(--text-2) mt-4">
            MapFeux regroupe les observations satellitaires en événements, les rattache à une
            commune, et indique pour chacun qui a observé quoi et quand.
          </p>

          <div className="mt-8 max-w-md">
            <MunicipalitySearch />
          </div>

          <p className="mt-5">
            <Link href="/carte" className="font-semibold underline underline-offset-4">
              Ouvrir la carte
            </Link>
            <span aria-hidden="true" className="text-(--border-strong) mx-3">
              /
            </span>
            <NearMe />
          </p>
        </div>

        {/*
          La carte nationale, vivante et non manipulable : un lien vers la
          carte, pas une carte. Le lavis départemental est la représentation
          faite pour ce zoom ; les marqueurs, eux, appartiennent à `/carte`.
        */}
        {/*
          16/10 en large : assez haut pour que la France se lise, assez bas
          pour que les trois chiffres tiennent dans le premier écran d'un
          1280 × 800 — en 5/4 ils tombaient sous le pli.
        */}
        <Link
          href="/carte"
          aria-label="Ouvrir la carte nationale"
          className="group relative block aspect-[4/3] overflow-hidden rounded-xl border sm:aspect-[16/11] lg:aspect-[16/10]"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <MapView
            className="h-full w-full"
            center={DEFAULT_VIEW.center}
            zoom={DEFAULT_VIEW.zoom}
            interactive={false}
            events={[]}
          />
          <span
            className="mono text-label absolute left-3 top-3 rounded-full border px-3 py-1"
            style={{
              background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
              borderColor: 'var(--border)',
              color: 'var(--text-2)',
              backdropFilter: 'blur(6px)',
            }}
          >
            carte nationale · 7 derniers jours
          </span>
          {/* En haut à droite, pas en bas : le bas droit est à l'attribution
              IGN, qui ne se recouvre pas (§9.5). */}
          <span
            className="text-small group-hover:border-(--border-strong) absolute right-3 top-3 rounded-full border px-3 py-1 font-semibold transition-colors"
            style={{
              background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
              borderColor: 'var(--border)',
              color: 'var(--text)',
              backdropFilter: 'blur(6px)',
            }}
          >
            Ouvrir la carte →
          </span>
        </Link>
      </div>

      {/*
        Trois chiffres, lus en base à l'instant du rendu. Ils ne disent pas
        « combien de feux » — MapFeux ne le sait pas — mais combien
        d'événements observés, sur combien de départements, avec combien de
        sources qui répondent : les trois choses qu'un service d'observation
        peut affirmer sans mentir.
      */}
      {anyUnreadable && (
        <UnavailableNotice className="mt-8 max-w-[68ch]">
          Certains chiffres n’ont pas pu être établis : la base n’a pas répondu au moment de rendre
          cette page. Un tiret n’est pas un zéro — rien ne dit qu’il n’y a pas d’événement. L’
          <Link href="/statut" className="underline underline-offset-4">
            état des données
          </Link>{' '}
          indique ce qui répond.
        </UnavailableNotice>
      )}

      {/* `mt-8` et non `mt-10` : à 1280 × 800, les trois chiffres passaient sous
          le pli de quinze pixels. Ils sont faits pour le premier écran. */}
      <ul className="mt-8 grid gap-3 sm:grid-cols-3">
        {figures.map((figure) => {
          const inner = (
            <>
              <span className="mono block text-[2rem] font-medium leading-none tracking-tight">
                {figure.value}
              </span>
              <span className="text-body mt-2 block font-semibold">{figure.label}</span>
              <span className="text-small text-(--text-3) mt-0.5 block">{figure.detail}</span>
            </>
          );
          return (
            <li
              key={figure.label}
              className="rounded-xl border p-5"
              style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
            >
              {figure.href === undefined ? (
                inner
              ) : (
                <Link href={figure.href} className="block">
                  {inner}
                </Link>
              )}
            </li>
          );
        })}
      </ul>

      {/*
        L'avertissement porte le filet orange du bandeau de positionnement : il
        relève de l'observation thermique, seul domaine auquel l'orange
        appartient. Même forme que les bandeaux d'état de la fiche événement.
      */}
      <div
        className="text-small mt-10 max-w-[68ch] rounded-md border-l-[3px] px-5 py-4"
        style={{
          background: 'var(--color-age-2-wash)',
          borderColor: 'var(--color-age-2)',
        }}
      >
        <h2 className="font-semibold">Ce que montre — et ne montre pas — cette carte</h2>
        <p className="mt-2">{MAP_DISCLAIMER}</p>
      </div>

      {departments.length > 0 && (
        <section className="mt-14 max-w-[68ch]">
          <h2 className="text-title font-bold tracking-tight">Territoires ouverts</h2>
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
            {departments.map((department) => (
              <li key={department.slug}>
                <Link
                  href={`/territoires/${department.slug}`}
                  className="underline underline-offset-4"
                >
                  {department.name} <span className="mono text-(--text-3)">{department.code}</span>
                </Link>
              </li>
            ))}
          </ul>
          {/*
            ⚠️ Formulation publique corrigée le 8 août sans validation métier
            préalable : la phrase précédente — « les détections ne sont
            importées que sur ces départements » — était fausse depuis la mise
            en service du 5 août, l'ingestion FIRMS couvrant la France entière.
            Les agrégats départementaux l'ont rendue visible. À faire relire.
          */}
          <p className="text-small text-(--text-2) mt-4">
            Les détections satellitaires couvrent la France entière. Ces territoires pilotes
            disposent en plus d’une page dédiée et de liens officiels vérifiés.
          </p>
        </section>
      )}

      <section className="mt-14 max-w-[68ch]">
        <h2 className="text-title font-bold tracking-tight">Comprendre avant d’interpréter</h2>
        <p className="text-(--text-2) mt-3">
          Une détection thermique n’est pas un feu confirmé, et son absence ne signifie pas qu’il
          n’y en a pas. La{' '}
          <Link href="/methodologie" className="underline underline-offset-4">
            méthodologie
          </Link>{' '}
          détaille ce que les satellites voient, ce qu’ils manquent, et comment un point devient un
          événement. L’
          <Link href="/statut" className="underline underline-offset-4">
            état des données
          </Link>{' '}
          indique en permanence quelles sources répondent.
        </p>
      </section>
    </div>
  );
}
