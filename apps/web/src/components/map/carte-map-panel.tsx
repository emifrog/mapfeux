'use client';

import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import { useEffect, useState, useSyncExternalStore } from 'react';

import { DEFAULT_WINDOW_HOURS } from '@/lib/map/time-windows';
import { resolveRadarTimeline, type RadarTimeline } from '@/lib/radar/timeline';

import type { AirTilesInfo } from './air-layer';
import type { MapEvent } from './event-layer';
import { FloatingCard } from './floating-card';
import { LayersPanel } from './layers-panel';
import { MapLegend } from './legend';
import { MapView } from './map-view';
import { TimeBar } from './time-bar';

/**
 * Coque d'application de `/carte` : la carte, et tout ce qui flotte dessus.
 *
 * Référence : cahier §19.1, §19.3, §21.3, FR-121.
 *
 * ## Hauteur et plein bord
 *
 * La carte occupe l'écran moins la coque fixe du site — en-tête et bandeau
 * de positionnement, mesurés à 172 px le 11 septembre 2026 en 1024 de
 * large. La valeur est en dur parce qu'aucune règle CSS ne la donne sans
 * JavaScript, et l'écart est sans conséquence : trop courte, il reste un
 * filet de page sous la carte ; trop longue, on défile de quelques pixels.
 * Ce qui se paierait cher, c'est un observateur de taille dans le gabarit
 * de toutes les pages pour une seule d'entre elles.
 *
 * Sous 640 px, rien ne flotte : la carte prend une hauteur franche et les
 * panneaux s'empilent dessous. Une commande posée sur une carte de
 * téléphone couvre la carte.
 *
 * ## Ce qui se lit à gauche, ce qui se manipule à droite
 *
 * `children` porte ce que le serveur a rendu — identité de la page, liste
 * textuelle — et la colonne de gauche y ajoute ce qui dépend de l'état :
 * la légende, puis la provenance des calques appelés. Le panneau de droite
 * ne porte que des commandes et leurs échelles.
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

/**
 * Le point de bascule des panneaux : 640 px, le `sm` de Tailwind.
 *
 * Il est lu en JavaScript parce que la caméra de MapLibre a besoin d'un
 * nombre, pas d'une classe : au-dessus de ce seuil les panneaux flottent et
 * mangent de la carte, en dessous ils s'empilent et n'en mangent plus. Deux
 * sources pour un même seuil ; celle-ci le nomme.
 */
const PANELS_FLOAT = '(min-width: 640px)';

function subscribePanelsFloat(callback: () => void): () => void {
  const query = window.matchMedia(PANELS_FLOAT);
  query.addEventListener('change', callback);
  return () => query.removeEventListener('change', callback);
}

function usePanelsFloat(): boolean {
  return useSyncExternalStore(
    subscribePanelsFloat,
    () => window.matchMedia(PANELS_FLOAT).matches,
    // Au rendu serveur, on suppose l'empilement : une marge posée sur un
    // téléphone décalerait la carte vers un vide.
    () => false,
  );
}

/**
 * Surface de carte mangée par les panneaux, en pixels.
 *
 * Ces nombres doublent des largeurs déclarées en CSS — 21 rem pour la
 * colonne de lecture, 16 rem pour les calques, 0,75 rem de gouttière — et
 * c'est le prix à payer : la caméra ne lit pas les feuilles de style. Les
 * mesurer à l'exécution demanderait un observateur de taille sur trois
 * panneaux pour gagner quelques pixels de justesse.
 */
const PANEL_PADDING = { top: 12, right: 268, bottom: 100, left: 348 } as const;

/** La même chose, colonne de lecture repliée. */
const PANEL_PADDING_FOLDED = { ...PANEL_PADDING, left: 56 } as const;

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
  children,
}: {
  events: MapEvent[];
  center: readonly [number, number];
  zoom: number;
  /** Cartons rendus par le serveur, en tête de la colonne de lecture. */
  children?: React.ReactNode;
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
  const panelsFloat = usePanelsFloat();

  // La colonne de lecture se replie. Ce n'est pas un confort : elle couvre
  // en permanence le tiers ouest de la carte, et les marqueurs d'une
  // journée peuvent tous s'y trouver — c'était le cas le 11 septembre
  // 2026, où la liste désignait neuf événements qu'elle cachait tous.
  // Ouverte par défaut : sans JavaScript elle reste là, et c'est le seul
  // chemin d'accès textuel de la page (§8.6).
  const [readingOpen, setReadingOpen] = useState(true);

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
    <div className="relative sm:h-[calc(100dvh-10.75rem)] sm:min-h-[30rem]">
      {/* La carte, à plein bord sous les cartons. Sur téléphone elle garde
          un cadre et des coins arrondis : elle y est un bloc de la page,
          pas la page. */}
      <div className="overflow-hidden max-sm:mx-3 max-sm:h-[60dvh] max-sm:min-h-[20rem] max-sm:rounded-lg max-sm:border sm:absolute sm:inset-0">
        <MapView
          center={center}
          zoom={zoom}
          className="h-full w-full"
          events={events}
          reloadOnMove
          {...(panelsFloat ? { padding: readingOpen ? PANEL_PADDING : PANEL_PADDING_FOLDED } : {})}
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

      {/*
        La couche des panneaux.

        Au-dessus de 640 px, c'est une grille posée sur la carte plutôt que
        trois panneaux calés chacun sur ses décalages : ils se chevauchaient
        dès que la barre temporelle passait à deux lignes, et aucun nombre
        écrit à l'avance ne pouvait le prévoir. Le cadre ne capte pas la
        souris — `pointer-events-none` —, chaque panneau si : la carte reste
        saisissable entre eux. Le retrait du bas réserve sa place à
        l'attribution IGN, qui ne se couvre jamais (§9.5).

        En dessous de 640 px, c'est une pile sous la carte, et l'ordre y est
        celui de la lecture : la fenêtre affichée, puis les calques, puis ce
        qu'il y a à lire.
      */}
      <div className="flex flex-col gap-3 max-sm:mx-3 max-sm:mt-3 sm:pointer-events-none sm:absolute sm:inset-0 sm:z-10 sm:p-3 sm:pb-12">
        <div className="flex min-h-0 flex-1 gap-3 max-sm:contents">
          <div
            id="colonne-lecture"
            // `hidden` ne s'applique qu'au-dessus de 640 px : sous ce seuil
            // la colonne est la page, elle ne se replie pas.
            className={`pointer-events-auto flex flex-col gap-3 max-sm:order-3 sm:w-[21rem] sm:overflow-y-auto sm:pr-1 ${
              readingOpen ? '' : 'sm:hidden'
            }`}
          >
            {children}

            <MapLegend />

            {(airInfo !== null || radarTimeline !== null) && (
              <FloatingCard labelledBy="provenance-calques">
                <h2
                  id="provenance-calques"
                  className="mono mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
                  style={{ color: 'var(--text)' }}
                >
                  D’où viennent les calques affichés
                </h2>

                {/* FR-121 : résolution, unité, heure et nature modélisée visibles. */}
                {airInfo !== null && (
                  <p className="text-small text-(--text-2) leading-relaxed">
                    <strong>Qualité de l’air</strong> — prévision du modèle{' '}
                    <span className="mono">{airInfo.model}</span>, run du{' '}
                    <time dateTime={airInfo.runAt} className="mono">
                      {TIME.format(new Date(airInfo.runAt))}
                    </time>
                    , valide le{' '}
                    <time dateTime={airInfo.validAt} className="mono">
                      {TIME.format(new Date(airInfo.validAt))}
                    </time>
                    , grille de {airInfo.resolution} (~11 km), en {airInfo.unit}. Source :
                    Copernicus Atmosphere Monitoring Service (CAMS). {MODELLED_VALUE_NOTICE}
                  </p>
                )}

                {radarTimeline !== null && (
                  <p className="text-small text-(--text-2) mt-3 leading-relaxed">
                    <strong>Radar</strong> — {radarTimeline.quantityLabel}. Sous{' '}
                    {radarTimeline.drawnFrom.toLocaleString('fr-FR')} {radarTimeline.unit}, rien
                    n’est dessiné. {radarTimeline.attribution}.
                  </p>
                )}
              </FloatingCard>
            )}
          </div>

          {/*
            Le repli de la colonne. Il ne se montre qu'au-dessus de 640 px,
            là où la colonne flotte sur la carte et la couvre.
          */}
          <button
            type="button"
            onClick={() => setReadingOpen(!readingOpen)}
            aria-expanded={readingOpen}
            aria-controls="colonne-lecture"
            className="mono pointer-events-auto h-8 shrink-0 self-start rounded-lg border px-2 text-[13px] shadow-lg max-sm:hidden"
            style={{
              background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
              borderColor: 'var(--border)',
              color: 'var(--text-2)',
              backdropFilter: 'blur(6px)',
            }}
          >
            <span aria-hidden="true">{readingOpen ? '‹' : '›'}</span>
            <span className="sr-only">
              {readingOpen ? 'Masquer le panneau de lecture' : 'Afficher le panneau de lecture'}
            </span>
          </button>

          {/*
            Le retrait du haut réserve le coin à la commande de zoom de
            MapLibre — 29 px à 10 px du bord —, qui était sinon recouverte :
            une carte dont on ne peut plus cliquer le « + ».
          */}
          <div className="max-sm:contents sm:ml-auto sm:flex sm:min-h-0 sm:w-64 sm:flex-col sm:pt-11">
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
        </div>

        <TimeBar windowHours={windowHours} onWindowHours={setWindowHours} eventCount={eventCount} />
      </div>
    </div>
  );
}
