import { MAP_DISCLAIMER } from '@mapfeux/domain';
import Link from 'next/link';

import { MunicipalitySearch } from '@/components/municipality-search';
import { fetchTerritories } from '@/lib/data/territories';

/**
 * Accueil.
 *
 * Référence : cahier §8.1. L'utilisateur doit comprendre en moins de cinq
 * secondes le territoire affiché, la période couverte et le caractère non
 * officiel du service. Les couches de détections arrivent avec le lot 3 : tant
 * qu'elles n'existent pas, la page le dit plutôt que d'afficher une carte vide
 * laissant croire à l'absence de tout phénomène.
 */

export const revalidate = 3600;

export default async function HomePage() {
  const territories = await fetchTerritories();
  const departments = territories.filter((territory) => territory.type === 'department');

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">
        Détections thermiques et fumées en France
      </h1>

      <p className="mt-4 text-stone-700">
        MapFeux regroupe les détections thermiques satellitaires en événements probables, estime un
        panache de fumée indicatif et identifie les communes potentiellement concernées.
      </p>

      <div className="mt-8 max-w-md">
        <MunicipalitySearch />
      </div>

      <p className="mt-4">
        <Link href="/carte" className="underline underline-offset-4">
          Ouvrir la carte nationale
        </Link>
      </p>

      <div className="mt-8 rounded border border-stone-300 bg-stone-50 p-4 text-sm text-stone-800">
        <h2 className="font-semibold">Ce que montre — et ne montre pas — cette carte</h2>
        <p className="mt-2">{MAP_DISCLAIMER}</p>
      </div>

      {departments.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold">Territoires ouverts</h2>
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
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-xl font-semibold">État de la plateforme</h2>
        <p className="mt-2 text-stone-700">
          Les détections satellitaires, les fiches événement et le panache indicatif sont en cours
          de construction. L’état des sources de données est déjà consultable.
        </p>
        <p className="mt-4">
          <Link href="/statut" className="underline underline-offset-4">
            Consulter l’état des données
          </Link>
        </p>
      </section>
    </div>
  );
}
