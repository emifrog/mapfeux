'use client';

import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import { useState } from 'react';

import { POLLUTANT_LABELS } from '@/lib/air/labels';

import type { AirTilesInfo } from './air-layer';
import type { MapEvent } from './event-layer';
import { MapLegend } from './legend';
import { MapView } from './map-view';

/**
 * Carte nationale et sa colonne de légendes, avec la couche air commutable.
 *
 * Référence : cahier §19.1 et FR-121.
 *
 * La couche est **éteinte par défaut** : la carte parle d'abord des
 * détections thermiques (§8.1), le champ modélisé est un contexte qu'on
 * appelle. Sa légende vient de l'alias publié — seuils, couleurs et version
 * de la palette qui a réellement coloré les tuiles — et porte l'heure de
 * validité, la résolution, l'unité et la nature modélisée (FR-121).
 */

const TIME = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

const CHOICES = [null, 'pm2_5', 'pm10'] as const;

/** « ≤ 20 », « 20–40 », « > 150 » — les bornes viennent de l'alias. */
function bandRange(bands: AirTilesInfo['bands'], index: number): string {
  const upper = bands[index]?.jusqu_a ?? null;
  const previous = index > 0 ? (bands[index - 1]?.jusqu_a ?? null) : null;
  if (previous === null) return `≤ ${upper ?? '∞'}`;
  if (upper === null) return `> ${previous}`;
  return `${previous}–${upper}`;
}

export function CarteMapPanel({
  events,
  center,
  zoom,
}: {
  events: MapEvent[];
  center: readonly [number, number];
  zoom: number;
}) {
  const [pollutant, setPollutant] = useState<string | null>(null);
  const [airInfo, setAirInfo] = useState<AirTilesInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const missing = pollutant !== null && !loading && airInfo === null;

  return (
    <div className="mt-8 grid gap-4 lg:grid-cols-[1fr_320px] lg:items-start">
      <div
        className="sm:h-104 lg:h-136 h-96 overflow-hidden rounded-lg border"
        style={{ borderColor: 'var(--border-strong)' }}
      >
        <MapView
          center={center}
          zoom={zoom}
          className="h-full w-full"
          events={events}
          reloadOnMove
          airPollutant={pollutant}
          onAirInfo={(info) => {
            setAirInfo(info);
            setLoading(false);
          }}
        />
      </div>

      <div className="grid gap-4">
        <MapLegend />

        <section
          aria-labelledby="legende-air"
          className="mono rounded-xl border p-3 text-[11px]"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text-2)',
          }}
        >
          <h2
            id="legende-air"
            className="mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
            style={{ color: 'var(--text)' }}
          >
            Qualité de l’air modélisée
          </h2>

          <fieldset>
            <legend className="sr-only">Couche de qualité de l’air affichée</legend>
            <div className="flex flex-wrap gap-1.5">
              {CHOICES.map((choice) => (
                <label
                  key={choice ?? 'off'}
                  className="cursor-pointer rounded-md border px-2 py-1"
                  style={{
                    borderColor: pollutant === choice ? 'var(--border-strong)' : 'var(--border)',
                    background: pollutant === choice ? 'var(--surface-muted)' : 'transparent',
                    color: pollutant === choice ? 'var(--text)' : 'var(--text-2)',
                  }}
                >
                  <input
                    type="radio"
                    name="couche-air"
                    className="sr-only"
                    checked={pollutant === choice}
                    onChange={() => {
                      setPollutant(choice);
                      setAirInfo(null);
                      setLoading(choice !== null);
                    }}
                  />
                  {choice === null ? 'Sans' : POLLUTANT_LABELS[choice]}
                </label>
              ))}
            </div>
          </fieldset>

          <div aria-live="polite">
            {missing && (
              <p className="mt-3 font-sans text-xs leading-relaxed">
                Aucune donnée modélisée récente : la couche ne s’affiche pas.
              </p>
            )}

            {airInfo !== null && (
              <>
                <ul className="mt-3 flex flex-col gap-1.5">
                  {airInfo.bands.map((band, index) => (
                    <li key={band.libelle} className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="rounded-xs block size-2.5 shrink-0"
                        style={{ backgroundColor: band.couleur }}
                      />
                      <span className="w-16 tabular-nums">{bandRange(airInfo.bands, index)}</span>
                      <span className="font-sans text-xs">{band.libelle}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 tabular-nums">
                  en {airInfo.unit} · grille {airInfo.resolution} · valide le{' '}
                  <time dateTime={airInfo.validAt}>{TIME.format(new Date(airInfo.validAt))}</time>
                </p>
                <p className="mt-2 font-sans text-xs leading-relaxed">
                  Prévision du modèle <span className="mono">{airInfo.model}</span>, run du{' '}
                  <time dateTime={airInfo.runAt} className="mono">
                    {TIME.format(new Date(airInfo.runAt))}
                  </time>
                  . {MODELLED_VALUE_NOTICE}
                </p>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
