import type { Metadata } from 'next';
import Link from 'next/link';

import { Prose, Section } from '@/components/prose';
import { fetchSourceStatus } from '@/lib/sources';

/**
 * Page des sources et attributions. Cahier §9.7 et FR-101.
 *
 * Les attributions sont lues dans le registre des sources, jamais recopiées
 * ici : une attribution en dur finirait par diverger de la licence réellement
 * enregistrée, et l'écart ne se verrait pas.
 */

export const metadata: Metadata = {
  title: 'Sources et licences',
  description: 'Origine, licence et attribution de chaque source de données utilisée par MapFeux.',
};

export const revalidate = 3600;

export default async function SourcesPage() {
  const result = await fetchSourceStatus();

  return (
    <Prose
      eyebrow="provenance"
      title="Sources et licences"
      lead="D’où viennent les données affichées, sous quelle licence, et ce que chacune permet de dire."
    >
      {!result.readable ? (
        <p>
          Le registre des sources n’est pas consultable actuellement. Les attributions ci-dessous ne
          peuvent donc pas être affichées.
        </p>
      ) : (
        <Section title="Registre">
          <ul className="flex flex-col gap-5">
            {result.sources.map((source) => (
              <li
                key={source.key}
                className="rounded-xl border p-4"
                style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
              >
                <p className="font-semibold">{source.name}</p>
                <p className="text-sm" style={{ color: 'var(--text-2)' }}>
                  {source.provider}
                  {source.license_name !== null && <> · licence {source.license_name}</>}
                </p>
                <p className="mt-2 text-sm">{source.attribution}</p>
                {source.documentation_url !== null && (
                  <p className="mono mt-2 text-xs">
                    <a
                      href={source.documentation_url}
                      rel="noopener noreferrer"
                      className="underline underline-offset-4"
                    >
                      documentation du fournisseur
                    </a>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Ce que chaque source permet — et ne permet pas">
        <p>
          <strong>NASA FIRMS</strong> fournit des anomalies thermiques, pas des incendies confirmés.
          La donnée est publiée en temps quasi réel, généralement dans les trois heures suivant le
          passage du satellite.
        </p>
        <p>
          <strong>IGN ADMIN EXPRESS</strong> fournit les limites communales. Elles servent à nommer
          un lieu, jamais à affirmer qu’une commune est menacée.
        </p>
        <p>
          <strong>Météo-France</strong> et <strong>Copernicus CAMS</strong> fournissent des sorties
          de modèles, à l’échelle de plusieurs kilomètres. Une valeur de modèle n’est pas une mesure
          prise à l’endroit consulté.
        </p>
      </Section>

      <Section title="Réutilisation">
        <p>
          Les données brutes appartiennent à leurs producteurs et restent soumises à leurs licences
          respectives. Si vous republiez une information issue de MapFeux, reprenez l’attribution du
          producteur ci-dessus, et non la nôtre.
        </p>
        <p>
          La façon dont ces données sont transformées est décrite sur la page{' '}
          <Link href="/methodologie" className="underline underline-offset-4">
            Méthodologie
          </Link>
          . Leur fraîcheur du moment est sur{' '}
          <Link href="/statut" className="underline underline-offset-4">
            État des données
          </Link>
          .
        </p>
      </Section>
    </Prose>
  );
}
