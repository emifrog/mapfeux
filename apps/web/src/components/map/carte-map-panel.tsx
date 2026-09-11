'use client';

import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import { useEffect, useState, useSyncExternalStore } from 'react';

import { DEFAULT_WINDOW_HOURS } from '@/lib/map/time-windows';
import { resolveRadarTimeline, type RadarTimeline } from '@/lib/radar/timeline';

import type { AirTilesInfo } from './air-layer';
import type { MapEvent } from './event-layer';
import { LayersPanel } from './layers-panel';
import { MapLegend } from './legend';
import { MapView } from './map-view';
import { TimeBar } from './time-bar';

/**
 * Carte nationale, ses calques et ce qu'il faut lire pour les comprendre.
 *
 * Référence : cahier §19.1, §19.3, §21.3, FR-121.
 *
 * ## Mise en page — refaite le 11 septembre 2026
 *
 * La carte occupe la hauteur de l'écran et les commandes se posent dessus.
 * La version précédente la contraignait à un quart de page sous un mur de
 * texte, avec une colonne de 320 px où trois paragraphes d'explication
 * prenaient la place des commandes : on regardait des points minuscules en
 * lisant ce qu'ils auraient signifié. Le partage est désormais net — le
 * panneau porte ce qui se manipule, le dessous de carte ce qui se lit.
 *
 * Les couches restent **éteintes par défaut** : la carte parle d'abord des
 * détections thermiques (§8.1), le reste est un contexte qu'on appelle.
 */

const TIME = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

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

export function CarteMapPanel({
  events,
  center,
  zoom,
}: {
  events: MapEvent[];
  center: readonly [number, number];
  zoom: number;
}) {
  // La fenêtre par défaut est celle du rendu serveur : le premier lot arrive
  // déjà filtré, la carte n'a rien à recharger au montage.
  const [windowHours, setWindowHours] = useState<number | null>(DEFAULT_WINDOW_HOURS);
  const [eventCount, setEventCount] = useState(events.length);

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

  const airMissing = pollutant !== null && !loading && airInfo === null;
  const radarMissing = radarOn && !radarLoading && radarTimeline === null;
  const currentRadarFrame = radarTimeline?.frames[radarIndex];
  const radarFrame =
    radarOn && radarTimeline !== null && currentRadarFrame !== undefined
      ? { url: currentRadarFrame.url, coordinates: radarTimeline.coordinates }
      : null;

  return (
    <>
      {/* Le conteneur porte la position du panneau ; la carte garde son
          `overflow-hidden` pour que ses coins restent arrondis. */}
      <div className="relative mt-8">
        <div
          className="h-[70vh] min-h-[26rem] overflow-hidden rounded-lg border"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <MapView
            center={center}
            zoom={zoom}
            className="h-full w-full"
            events={events}
            reloadOnMove
            windowHours={windowHours}
            onEventsLoaded={setEventCount}
            airPollutant={pollutant}
            onAirInfo={(info) => {
              setAirInfo(info);
              setLoading(false);
            }}
            radarFrame={radarFrame}
          />
        </div>

        <TimeBar windowHours={windowHours} onWindowHours={setWindowHours} eventCount={eventCount} />

        <LayersPanel
          pollutant={pollutant}
          onPollutant={(choice) => {
            setPollutant(choice);
            setAirInfo(null);
            setLoading(choice !== null);
          }}
          airInfo={airInfo}
          airMissing={airMissing}
          radarOn={radarOn}
          onRadarOn={(on) => {
            setRadarOn(on);
            setRadarPlaying(false);
            if (on) {
              setRadarLoading(true);
            } else {
              setRadarTimeline(null);
            }
          }}
          radarTimeline={radarTimeline}
          radarMissing={radarMissing}
          radarIndex={radarIndex}
          onRadarIndex={setRadarIndex}
          playing={playing}
          onPlaying={setRadarPlaying}
          reducedMotion={reducedMotion}
          timeFormat={TIME}
        />
      </div>

      {/* Sous la carte : ce qui se lit. La légende d'âge d'abord — c'est
          elle qui décode les marqueurs —, puis la provenance des couches
          appelées, qui n'existe que lorsqu'elles sont affichées. */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[320px_1fr] lg:items-start">
        <MapLegend />

        {(airInfo !== null || radarTimeline !== null) && (
          <section
            aria-labelledby="provenance-calques"
            className="rounded-xl border p-4"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <h2
              id="provenance-calques"
              className="mono mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
              style={{ color: 'var(--text)' }}
            >
              D’où viennent les calques affichés
            </h2>

            {/* FR-121 : résolution, unité, heure et nature modélisée visibles. */}
            {airInfo !== null && (
              <p className="text-small text-(--text-2) max-w-[68ch]">
                <strong>Qualité de l’air</strong> — prévision du modèle{' '}
                <span className="mono">{airInfo.model}</span>, run du{' '}
                <time dateTime={airInfo.runAt} className="mono">
                  {TIME.format(new Date(airInfo.runAt))}
                </time>
                , valide le{' '}
                <time dateTime={airInfo.validAt} className="mono">
                  {TIME.format(new Date(airInfo.validAt))}
                </time>
                , grille de {airInfo.resolution} (~11 km), en {airInfo.unit}. Source : Copernicus
                Atmosphere Monitoring Service (CAMS). {MODELLED_VALUE_NOTICE}
              </p>
            )}

            {radarTimeline !== null && (
              <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">
                <strong>Radar</strong> — {radarTimeline.quantityLabel}. Sous{' '}
                {radarTimeline.drawnFrom.toLocaleString('fr-FR')} {radarTimeline.unit}, rien n’est
                dessiné. {radarTimeline.attribution}.
              </p>
            )}
          </section>
        )}
      </div>
    </>
  );
}
