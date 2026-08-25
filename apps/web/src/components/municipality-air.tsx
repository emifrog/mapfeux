import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import Link from 'next/link';

import { POLLUTANT_LABELS } from '@/lib/air/labels';
import { fetchAirSamples } from '@/lib/data/air';

/**
 * Qualité de l'air modélisée sur la fiche commune. Cahier §19.2 et FR-121.
 *
 * Chaque champ exigé par le §19.2 est affiché : valeur, unité, polluant,
 * heure de validité, résolution, méthode d'échantillonnage, source, et
 * l'avertissement « donnée modélisée ». La valeur est une mesure : chasse
 * fixe ; tout le reste est de la provenance.
 *
 * Sans donnée récente, la section le dit — conditionnée à la donnée, pas au
 * calendrier : la phrase reste vraie que la source soit à venir, en panne ou
 * en retard (le piège des phrases d'attente, plan §15).
 */

const TIME = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

export async function MunicipalityAir({
  longitude,
  latitude,
}: {
  longitude: number;
  latitude: number;
}) {
  const samples = await fetchAirSamples(longitude, latitude);
  const fresh = samples.filter((sample) => !sample.stale);
  const first = fresh[0];

  return (
    <section className="mt-12" aria-labelledby="qualite-air">
      <h2 id="qualite-air" className="text-title font-bold tracking-tight">
        Qualité de l’air modélisée
      </h2>

      {first === undefined ? (
        <p className="text-(--text-2) mt-3 max-w-[68ch]">
          Aucune valeur modélisée récente n’est disponible pour cette commune. L’
          <Link href="/statut" className="underline underline-offset-4">
            état des données
          </Link>{' '}
          indique la situation de la source.
        </p>
      ) : (
        <>
          <dl className="mt-4 flex flex-wrap gap-x-10 gap-y-4">
            {fresh.map((sample) => (
              <div key={sample.pollutant}>
                <dt className="text-small text-(--text-2)">
                  {POLLUTANT_LABELS[sample.pollutant] ?? sample.pollutant}
                </dt>
                <dd className="mono text-title mt-1 font-semibold">
                  {sample.value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}{' '}
                  <span className="text-small text-(--text-2) font-normal">{sample.unit}</span>
                </dd>
                <dd className="text-micro text-(--text-3) mt-1">
                  valide le{' '}
                  <time dateTime={sample.validAt} className="mono">
                    {TIME.format(new Date(sample.validAt))}
                  </time>
                </dd>
              </div>
            ))}
          </dl>

          {/* FR-121 : résolution, unité, heure et nature modélisée visibles ;
              §19.2 : la méthode et la source font partie de la réponse. */}
          <p className="text-small text-(--text-3) mt-4 max-w-[68ch]">
            Prévision du modèle <span className="mono">{first.model}</span>, run du{' '}
            <time dateTime={first.runAt} className="mono">
              {TIME.format(new Date(first.runAt))}
            </time>
            , grille de {first.resolution} (~11 km), {first.samplingMethod}. Source : Copernicus
            Atmosphere Monitoring Service (CAMS).
          </p>
          <p className="text-small text-(--text-3) mt-2 max-w-[68ch]">{MODELLED_VALUE_NOTICE}</p>
        </>
      )}
    </section>
  );
}
