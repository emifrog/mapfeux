import { MAP_DISCLAIMER } from '@mapfeux/domain';
import Link from 'next/link';

import { MunicipalitySearch } from '@/components/municipality-search';
import { NearMe } from '@/components/near-me';
import { fetchTerritories } from '@/lib/data/territories';

/**
 * Accueil. Cahier §8.1.
 *
 * L'utilisateur doit comprendre en moins de cinq secondes ce que le service
 * montre, sur quel territoire, et son caractère non officiel. La recherche est
 * placée avant tout le reste : c'est la seule action que quelqu'un vient
 * réellement faire ici.
 *
 * Cette passe ne touche que la forme. Le libellé du titre relève d'une
 * formulation publique, qui passe par une validation métier avant d'être
 * modifiée — voir les règles de contribution du dépôt.
 */

export const revalidate = 3600;

export default async function HomePage() {
  const territories = await fetchTerritories();
  const departments = territories.filter((territory) => territory.type === 'department');

  return (
    <div className="shell max-w-[68ch] py-14">
      <p className="eyebrow mb-3">observation satellitaire · France</p>

      <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Où sont les détections thermiques en France
      </h1>

      <p className="text-lead text-(--text-2) mt-4">
        MapFeux regroupe les observations satellitaires en événements, les rattache à une commune,
        et indique pour chacun qui a observé quoi et quand.
      </p>

      <div className="mt-9 max-w-md">
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

      {/*
        L'avertissement porte le filet orange du bandeau de positionnement : il
        relève de l'observation thermique, seul domaine auquel l'orange
        appartient. Même forme que les bandeaux d'état de la fiche événement.
      */}
      <div
        className="text-small mt-10 rounded-md border-l-[3px] px-5 py-4"
        style={{
          background: 'var(--color-age-2-wash)',
          borderColor: 'var(--color-age-2)',
        }}
      >
        <h2 className="font-semibold">Ce que montre — et ne montre pas — cette carte</h2>
        <p className="mt-2">{MAP_DISCLAIMER}</p>
      </div>

      {departments.length > 0 && (
        <section className="mt-14">
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

      <section className="mt-14">
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
