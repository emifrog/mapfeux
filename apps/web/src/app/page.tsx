import { MAP_DISCLAIMER } from '@mapfeux/domain';
import Link from 'next/link';

import { MunicipalitySearch } from '@/components/municipality-search';
import { fetchTerritories } from '@/lib/data/territories';

/**
 * Accueil. Cahier §8.1.
 *
 * L'utilisateur doit comprendre en moins de cinq secondes ce que le service
 * montre, sur quel territoire, et son caractère non officiel. La recherche est
 * placée avant tout le reste : c'est la seule action que quelqu'un vient
 * réellement faire ici.
 */

export const revalidate = 3600;

export default async function HomePage() {
  const territories = await fetchTerritories();
  const departments = territories.filter((territory) => territory.type === 'department');

  return (
    <div className="mx-auto max-w-[68ch] px-6 py-14">
      <h1 className="text-4xl font-bold tracking-tight">
        Où sont les détections thermiques en France
      </h1>
      <p className="mt-4 text-lg" style={{ color: 'var(--text-2)' }}>
        MapFeux regroupe les observations satellitaires en événements, les rattache à une commune,
        et indique pour chacun qui a observé quoi et quand.
      </p>

      <div className="mt-9 max-w-md">
        <MunicipalitySearch />
      </div>

      <p className="mt-5">
        <Link href="/carte" className="font-medium underline underline-offset-4">
          Ouvrir la carte
        </Link>
      </p>

      <div
        className="mt-10 rounded-2xl border-l-4 p-5 text-sm"
        style={{
          background: 'var(--color-age-2-wash)',
          borderColor: 'var(--color-age-2)',
        }}
      >
        <h2 className="font-semibold">Ce que montre — et ne montre pas — cette carte</h2>
        <p className="mt-2">{MAP_DISCLAIMER}</p>
      </div>

      {departments.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl font-semibold tracking-tight">Territoires ouverts</h2>
          <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
            {departments.map((department) => (
              <li key={department.slug}>
                <Link
                  href={`/territoire/${department.slug}`}
                  className="underline underline-offset-4"
                >
                  {department.name} ({department.code})
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm" style={{ color: 'var(--text-2)' }}>
            Les détections ne sont importées que sur ces départements. Ailleurs, l’absence
            d’événement ne signifie rien.
          </p>
        </section>
      )}

      <section className="mt-12">
        <h2 className="text-xl font-semibold tracking-tight">Comprendre avant d’interpréter</h2>
        <p className="mt-2" style={{ color: 'var(--text-2)' }}>
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
