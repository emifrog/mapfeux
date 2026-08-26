'use client';

import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import { useEffect, useState, useSyncExternalStore } from 'react';

import { POLLUTANT_LABELS } from '@/lib/air/labels';
import { resolveRadarTimeline, type RadarTimeline } from '@/lib/radar/timeline';

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

/** Rythme de l'animation radar : un pas toutes les 600 ms (§19.3). */
const RADAR_STEP_MS = 600;

/**
 * `prefers-reduced-motion`, suivi en direct. Avec la réduction demandée, la
 * lecture automatique disparaît — le pas-à-pas reste : avancer d'une frame
 * sur un geste n'est pas une animation (§19.3, même doctrine et même
 * mécanique `useSyncExternalStore` que la relecture temporelle).
 */
function subscribeReducedMotion(callback: () => void): () => void {
  const query = window.matchMedia('(prefers-reduced-motion: reduce)');
  query.addEventListener('change', callback);
  return () => query.removeEventListener('change', callback);
}

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    () => false,
  );
}

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

  const [radarOn, setRadarOn] = useState(false);
  const [radarTimeline, setRadarTimeline] = useState<RadarTimeline | null>(null);
  const [radarLoading, setRadarLoading] = useState(false);
  const [radarIndex, setRadarIndex] = useState(0);
  const [radarPlaying, setRadarPlaying] = useState(false);
  const reducedMotion = usePrefersReducedMotion();

  // Activation : la timeline se résout, la frame la plus récente s'affiche
  // d'abord (FR-123) — la lecture, elle, n'est jamais automatique. Les
  // remises à zéro vivent dans le gestionnaire du sélecteur ; l'effet ne
  // pose d'état que depuis le rappel asynchrone.
  useEffect(() => {
    if (!radarOn) return;
    let cancelled = false;
    void resolveRadarTimeline().then((timeline) => {
      if (cancelled) return;
      setRadarTimeline(timeline);
      setRadarIndex(timeline === null ? 0 : timeline.frames.length - 1);
      setRadarLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [radarOn]);

  // Préchargement progressif (§19.3) : les frames entrent une à une dans le
  // cache du navigateur — la lecture trouve des images déjà là.
  useEffect(() => {
    if (radarTimeline === null) return;
    let cancelled = false;
    const preload = async (): Promise<void> => {
      for (const frame of radarTimeline.frames) {
        if (cancelled) return;
        await new Promise<void>((resolve) => {
          const image = new Image();
          image.onload = () => resolve();
          image.onerror = () => resolve();
          image.src = frame.url;
        });
      }
    };
    void preload();
    return () => {
      cancelled = true;
    };
  }, [radarTimeline]);

  // La lecture effective se dérive : la réduction des animations demandée
  // la coupe sans écrire d'état — et sans la faire repartir toute seule si
  // la préférence revient, puisque le bouton reflète le même dérivé.
  const playing = radarPlaying && !reducedMotion;

  // Lecture : un pas à la fois, en boucle.
  useEffect(() => {
    if (!playing || radarTimeline === null || radarTimeline.frames.length < 2) return;
    const timer = setInterval(() => {
      setRadarIndex((index) => (index + 1) % radarTimeline.frames.length);
    }, RADAR_STEP_MS);
    return () => clearInterval(timer);
  }, [playing, radarTimeline]);

  const missing = pollutant !== null && !loading && airInfo === null;
  const radarMissing = radarOn && !radarLoading && radarTimeline === null;
  const currentRadarFrame = radarTimeline?.frames[radarIndex];
  const radarFrame =
    radarOn && radarTimeline !== null && currentRadarFrame !== undefined
      ? { url: currentRadarFrame.url, coordinates: radarTimeline.coordinates }
      : null;

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
          radarFrame={radarFrame}
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

        <section
          aria-labelledby="legende-radar"
          className="mono rounded-xl border p-3 text-[11px]"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text-2)',
          }}
        >
          <h2
            id="legende-radar"
            className="mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
            style={{ color: 'var(--text)' }}
          >
            Radar de précipitations
          </h2>

          <fieldset>
            <legend className="sr-only">Couche radar affichée</legend>
            <div className="flex flex-wrap gap-1.5">
              {[false, true].map((choice) => (
                <label
                  key={String(choice)}
                  className="cursor-pointer rounded-md border px-2 py-1"
                  style={{
                    borderColor: radarOn === choice ? 'var(--border-strong)' : 'var(--border)',
                    background: radarOn === choice ? 'var(--surface-muted)' : 'transparent',
                    color: radarOn === choice ? 'var(--text)' : 'var(--text-2)',
                  }}
                >
                  <input
                    type="radio"
                    name="couche-radar"
                    className="sr-only"
                    checked={radarOn === choice}
                    onChange={() => {
                      setRadarOn(choice);
                      setRadarPlaying(false);
                      if (choice) {
                        setRadarLoading(true);
                      } else {
                        setRadarTimeline(null);
                      }
                    }}
                  />
                  {choice ? 'Lame d’eau' : 'Sans'}
                </label>
              ))}
            </div>
          </fieldset>

          <div aria-live="polite">
            {radarMissing && (
              <p className="mt-3 font-sans text-xs leading-relaxed">
                Aucune frame radar récente : la couche ne s’affiche pas.
              </p>
            )}

            {radarTimeline !== null && currentRadarFrame !== undefined && (
              <>
                {/* FR-123 : la frame et son heure d'acquisition, toujours. */}
                <p className="mt-3 tabular-nums">
                  frame{' '}
                  <span>
                    {radarIndex + 1}/{radarTimeline.frames.length}
                  </span>{' '}
                  · acquise le{' '}
                  <time dateTime={currentRadarFrame.acquiredAt.toISOString()}>
                    {TIME.format(currentRadarFrame.acquiredAt)}
                  </time>
                </p>

                <div className="mt-2 flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    className="rounded-md border px-2 py-1"
                    style={{ borderColor: 'var(--border)' }}
                    onClick={() => {
                      setRadarPlaying(false);
                      setRadarIndex(
                        (radarIndex - 1 + radarTimeline.frames.length) %
                          radarTimeline.frames.length,
                      );
                    }}
                  >
                    ◀ précédente
                  </button>
                  <button
                    type="button"
                    className="rounded-md border px-2 py-1"
                    style={{ borderColor: 'var(--border)' }}
                    onClick={() => {
                      setRadarPlaying(false);
                      setRadarIndex((radarIndex + 1) % radarTimeline.frames.length);
                    }}
                  >
                    suivante ▶
                  </button>
                  {/* La lecture automatique n'existe pas quand la réduction
                      des animations est demandée ; le pas-à-pas, si. */}
                  {!reducedMotion && radarTimeline.frames.length > 1 && (
                    <button
                      type="button"
                      className="rounded-md border px-2 py-1"
                      style={{
                        borderColor: playing ? 'var(--border-strong)' : 'var(--border)',
                        background: playing ? 'var(--surface-muted)' : 'transparent',
                      }}
                      onClick={() => setRadarPlaying(!playing)}
                    >
                      {playing ? '⏸ pause' : '▶ lecture'}
                    </button>
                  )}
                </div>

                <ul className="mt-3 flex flex-col gap-1.5">
                  {radarTimeline.bands.map((band, index) => (
                    <li key={band.libelle} className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="rounded-xs block size-2.5 shrink-0"
                        style={{ backgroundColor: band.couleur }}
                      />
                      <span className="w-16 tabular-nums">
                        {index === 0
                          ? `≤ ${band.jusqu_a ?? '∞'}`
                          : band.jusqu_a === null
                            ? `> ${radarTimeline.bands[index - 1]?.jusqu_a ?? ''}`
                            : `${radarTimeline.bands[index - 1]?.jusqu_a ?? ''}–${band.jusqu_a}`}
                      </span>
                      <span className="font-sans text-xs">{band.libelle}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 font-sans text-xs leading-relaxed">
                  Intensités en {radarTimeline.unit} ; {radarTimeline.quantityLabel}. Sous{' '}
                  {radarTimeline.drawnFrom.toLocaleString('fr-FR')} {radarTimeline.unit}, rien n’est
                  dessiné. {radarTimeline.attribution}.
                </p>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
