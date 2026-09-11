'use client';

import { MODELLED_VALUE_NOTICE } from '@mapfeux/domain';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';

import { EventList } from '@/components/event-list';
import type { EventSummary } from '@/lib/data/events';
import type { FramingBounds } from '@/lib/map/framing';
import { toEventSummaries } from '@/lib/map/loaded-events';
import { overlayPadding, type Inset, type OverlayPanel } from '@/lib/map/overlay-padding';
import { DEFAULT_WINDOW_HOURS, windowPhrase } from '@/lib/map/time-windows';
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
 * La carte prend tout ce que le gabarit lui laisse entre l'en-tête et le
 * pied de page, et la page tient dans l'écran. `data-shell="carte"` est la
 * prise par laquelle `globals.css` le règle, en répartition de colonne
 * plutôt qu'en hauteur écrite à la main : une première version réservait
 * 10,75 rem pour l'en-tête, mesurées un soir, qu'il aurait fallu corriger
 * à chaque retouche de celui-ci.
 *
 * Sous 640 px, rien ne flotte : la carte prend une hauteur franche et les
 * panneaux s'empilent dessous. Une commande posée sur une carte de
 * téléphone couvre la carte.
 *
 * ## Ce qui se lit à gauche, ce qui se manipule à droite
 *
 * `children` porte l'identité de la page, rendue par le serveur. La colonne
 * y ajoute ce qui vit : la **liste textuelle**, qui suit la carte (§8.6),
 * la légende, puis la provenance des calques appelés. Le panneau de droite
 * ne porte que des commandes et leurs échelles.
 *
 * ## La liste suit la carte
 *
 * Elle ne le faisait pas, et la page s'en excusait par écrit. Le
 * 11 septembre 2026, la barre annonçait 19 événements et le carton voisin
 * en annonçait 8 : aucun ne mentait, ensemble ils étaient illisibles. La
 * carte tient déjà la réponse — elle vient de la demander pour dessiner ses
 * marqueurs. Le premier état de la liste reste celui du rendu serveur, qui
 * est le seul à exister sans JavaScript.
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
 * Surface de carte mangée par les panneaux, **mesurée**.
 *
 * La caméra de MapLibre a besoin de nombres ; la feuille de style n'en
 * donne pas. Une première version les recopiait à la main et s'est trompée
 * deux fois dans la même soirée — la barre temporelle avait grandi, et elle
 * passe à deux lignes sur un écran étroit. Les panneaux se mesurent donc
 * eux-mêmes, et c'est la géométrie qui dit s'ils recouvrent la carte : sous
 * 640 px ils s'empilent dessous, leur retrait tombe à zéro sans qu'aucun
 * seuil ne soit écrit ici.
 *
 * L'observateur suit les trois panneaux **et** la carte : une fenêtre
 * redimensionnée, une barre qui passe à deux lignes, une colonne repliée,
 * une échelle de couche qui apparaît — tout cela change la zone utile, et
 * tout cela est un changement de taille.
 */
function useOverlayPadding(
  hostRef: React.RefObject<HTMLElement | null>,
  overlayRef: React.RefObject<HTMLElement | null>,
  /** Change quand la composition des panneaux change — un repli, par exemple. */
  layoutToken: unknown,
): Inset | null {
  const [inset, setInset] = useState<Inset | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    const overlay = overlayRef.current;
    if (host === null || overlay === null) return;

    const measure = (): void => {
      const panels: OverlayPanel[] = [...overlay.querySelectorAll('[data-overlay-side]')].map(
        (element) => ({
          side: element.getAttribute('data-overlay-side') as OverlayPanel['side'],
          rect: element.getBoundingClientRect(),
        }),
      );
      setInset(overlayPadding(host.getBoundingClientRect(), panels));
    };

    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(host);
    for (const element of overlay.querySelectorAll('[data-overlay-side]')) {
      observer.observe(element);
    }
    return () => observer.disconnect();
    // Les panneaux observés changent avec le repli de la colonne : l'effet
    // se rejoue pour rebrancher l'observateur sur ceux qui existent.
  }, [hostRef, overlayRef, layoutToken]);

  return inset;
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
  listEvents: initialListEvents,
  bounds,
  now: initialNow,
  children,
}: {
  events: MapEvent[];
  center: readonly [number, number];
  zoom: number;
  /** Le même premier lot, sous la forme que lit la liste textuelle. */
  listEvents: EventSummary[];
  /** Étendue des événements servis, à faire tenir dans la zone visible. */
  bounds: FramingBounds | null;
  /** Instant du rendu serveur : l'âge du premier lot se mesure contre lui. */
  now: Date;
  /** Cartons rendus par le serveur, en tête de la colonne de lecture. */
  children?: React.ReactNode;
}) {
  // La fenêtre par défaut est celle du rendu serveur : le premier lot arrive
  // déjà filtré, la carte n'a rien à recharger au montage.
  const [windowHours, setWindowHours] = useState<number | null>(DEFAULT_WINDOW_HOURS);

  // La liste **suit la carte** (§8.6). Elle part de ce que le serveur a rendu
  // — c'est le seul état sans JavaScript — et se remplace à chaque
  // chargement de la carte, qui a déjà demandé la réponse pour ses
  // marqueurs. L'instant de référence suit le même chemin : recalculer un
  // « il y a tant » au rendu ferait diverger serveur et client.
  const [listEvents, setListEvents] = useState(initialListEvents);
  const [listAt, setListAt] = useState(initialNow);
  const [listFollowsMap, setListFollowsMap] = useState(false);

  const [pollutant, setPollutant] = useState<string | null>(null);
  const [airInfo, setAirInfo] = useState<AirTilesInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const [radarOn, setRadarOn] = useState(false);
  const [radarTimeline, setRadarTimeline] = useState<RadarTimeline | null>(null);
  const [radarLoading, setRadarLoading] = useState(false);
  const [radarIndex, setRadarIndex] = useState(0);
  const [radarPlaying, setRadarPlaying] = useState(false);
  const reducedMotion = usePrefersReducedMotion();

  const mapHostRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  // La colonne de lecture se replie. Ce n'est pas un confort : elle couvre
  // en permanence le tiers ouest de la carte, et les marqueurs d'une
  // journée peuvent tous s'y trouver — c'était le cas le 11 septembre
  // 2026, où la liste désignait neuf événements qu'elle cachait tous.
  // Ouverte par défaut : sans JavaScript elle reste là, et c'est le seul
  // chemin d'accès textuel de la page (§8.6).
  const [readingOpen, setReadingOpen] = useState(true);

  const padding = useOverlayPadding(mapHostRef, overlayRef, readingOpen);

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
    <div data-shell="carte" className="relative sm:h-full sm:min-h-[24rem]">
      {/* La carte, à plein bord sous les cartons. Sur téléphone elle garde
          un cadre et des coins arrondis : elle y est un bloc de la page,
          pas la page. */}
      <div
        ref={mapHostRef}
        className="overflow-hidden max-sm:mx-3 max-sm:h-[60dvh] max-sm:min-h-[20rem] max-sm:rounded-lg max-sm:border sm:absolute sm:inset-0"
      >
        <MapView
          center={center}
          zoom={zoom}
          className="h-full w-full"
          events={events}
          reloadOnMove
          {...(padding === null ? {} : { padding })}
          {...(bounds === null ? {} : { fitBounds: bounds })}
          windowHours={windowHours}
          onEventsLoaded={(loaded) => {
            setListEvents(toEventSummaries(loaded));
            setListAt(new Date());
            setListFollowsMap(true);
          }}
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
      <div
        ref={overlayRef}
        className="flex flex-col gap-3 max-sm:mx-3 max-sm:mt-3 sm:pointer-events-none sm:absolute sm:inset-0 sm:z-10 sm:p-3 sm:pb-12"
      >
        <div className="flex min-h-0 flex-1 gap-3 max-sm:contents">
          <div
            id="colonne-lecture"
            data-overlay-side="left"
            // `hidden` ne s'applique qu'au-dessus de 640 px : sous ce seuil
            // la colonne est la page, elle ne se replie pas.
            className={`pointer-events-auto flex flex-col gap-3 max-sm:order-3 sm:w-[21rem] sm:overflow-y-auto sm:pr-1 ${
              readingOpen ? '' : 'sm:hidden'
            }`}
          >
            {children}

            {/*
              La liste textuelle (§8.6). Elle montre exactement ce que la
              carte montre — même emprise, même fenêtre — parce qu'elle lit
              la réponse que la carte vient d'obtenir. Tant que la carte n'a
              rien rechargé, c'est le lot du rendu serveur, et la phrase le
              dit : une liste qui prétendrait suivre avant de suivre serait
              pire que celle qui ne suivait pas.
            */}
            <FloatingCard labelledBy="liste">
              <h2 id="liste" className="text-body font-bold tracking-tight">
                Événements de la zone
              </h2>
              <p className="text-small text-(--text-2) mt-1.5 leading-relaxed" aria-live="polite">
                <span className="mono">{listEvents.length}</span> événement
                {listEvents.length > 1 ? 's' : ''} {windowPhrase(windowHours)}
                {listFollowsMap ? ', dans l’emprise affichée.' : ', au chargement de la page.'}{' '}
                Relevé à{' '}
                <time dateTime={listAt.toISOString()} className="mono">
                  {TIME.format(listAt)}
                </time>
                .
              </p>

              <div className="mt-4">
                <EventList events={listEvents} now={listAt} />
              </div>
            </FloatingCard>

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
          <div
            data-overlay-side="right"
            className="max-sm:contents sm:ml-auto sm:flex sm:min-h-0 sm:w-64 sm:flex-col sm:pt-11"
          >
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

        <TimeBar
          windowHours={windowHours}
          onWindowHours={setWindowHours}
          eventCount={listEvents.length}
        />
      </div>
    </div>
  );
}
