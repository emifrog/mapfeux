import { MAP_DISCLAIMER } from '@mapfeux/domain';
import Link from 'next/link';

/**
 * Accueil.
 *
 * La carte nationale (FR-001 à FR-007) est livrée avec EPIC-02, une fois les
 * géométries IGN importées. Cette page tient volontairement lieu de socle : il
 * vaut mieux une page honnête qu'une carte vide laissant croire à une absence
 * de détections.
 */
export default function HomePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">
        Détections thermiques et fumées en France
      </h1>

      <p className="mt-4 text-stone-700">
        MapFeux regroupe les détections thermiques satellitaires en événements probables, estime un
        panache de fumée indicatif et identifie les communes potentiellement concernées.
      </p>

      <div className="mt-8 rounded border border-stone-300 bg-stone-50 p-4 text-sm text-stone-800">
        <h2 className="font-semibold">Ce que montre — et ne montre pas — cette carte</h2>
        <p className="mt-2">{MAP_DISCLAIMER}</p>
      </div>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">État de la plateforme</h2>
        <p className="mt-2 text-stone-700">
          La carte nationale, la recherche de commune et les fiches événement sont en cours de
          construction. L’état des sources de données est déjà consultable.
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
