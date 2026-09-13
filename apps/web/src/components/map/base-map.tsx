'use client';

import { DEFAULT_VIEW, IGN_ATTRIBUTION, withoutRetinaSprite } from '@mapfeux/map-style';
import maplibregl from 'maplibre-gl';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { Protocol } from 'pmtiles';

import { publicEnv } from '@/lib/env';
import { applyBasemapStyle, isDarkTheme, subscribeTheme } from '@/lib/map/basemap-style';
import type { LoadedEventRow } from '@/lib/map/loaded-events';

import { removeAirLayer, resolveAirTiles, setAirLayer, type AirTilesInfo } from './air-layer';
import { removeRadarLayer, setRadarFrame, type RadarFrameDisplay } from './radar-layer';
import {
  addDepartmentLayer,
  DEPARTMENTS_FILL_LAYER_ID,
  setDepartmentAggregates,
  type DepartmentAggregate,
} from './department-layer';
import {
  addEventLayer,
  CLICKABLE_LAYER_IDS,
  EVENTS_CIRCLE_LAYER_ID,
  EVENTS_GLOW_LAYER_ID,
  EVENTS_HALO_LAYER_ID,
  EVENTS_TAIL_LAYER_ID,
  updateEventLayer,
  type MapEvent,
} from './event-layer';
import { addPerimeterLayer, updatePerimeterLayer, type PerimeterShape } from './perimeter-layer';

import 'maplibre-gl/dist/maplibre-gl.css';

// Le protocole `pmtiles://` s'enregistre une fois pour tout le module : c'est
// un registre global de MapLibre, pas un état de composant.
let pmtilesProtocolRegistered = false;

function registerPmtilesProtocol(): void {
  if (pmtilesProtocolRegistered) return;
  maplibregl.addProtocol('pmtiles', new Protocol().tile);
  pmtilesProtocolRegistered = true;
}

/**
 * URL de l'archive de tuiles courante, résolue par l'alias publié à côté
 * d'elle. L'archive porte son empreinte dans son nom et se met en cache un
 * an ; l'alias, minuscule et à cache court, est le seul point mutable —
 * c'est la bascule atomique du §21.1.
 */
async function resolveTilesUrl(): Promise<string | null> {
  const base = `${publicEnv.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/tiles`;
  try {
    const response = await fetch(`${base}/limites-administratives.json`);
    if (!response.ok) return null;
    const alias = (await response.json()) as { objet?: string };
    return typeof alias.objet === 'string' ? `${base}/${alias.objet}` : null;
  } catch {
    return null;
  }
}

/**
 * Agrégats départementaux des sept derniers jours. FR-003.
 *
 * Un échec laisse simplement les départements sans lavis : le fond, les
 * contours et les événements restent — une couche indisponible ne condamne
 * jamais la carte (§2.4).
 */
async function loadDepartmentAggregates(map: maplibregl.Map): Promise<void> {
  try {
    const response = await fetch('/api/v1/events/departments');
    if (!response.ok) return;
    const payload = (await response.json()) as { data: DepartmentAggregate[] };
    setDepartmentAggregates(map, payload.data);
  } catch {
    // Silencieux : voir ci-dessus.
  }
}

/**
 * Carte MapLibre.
 *
 * Référence : cahier §8.3 et §6.5.
 *
 * Accessibilité : MapLibre gère la navigation clavier sur son canevas, mais une
 * carte reste inaccessible aux lecteurs d'écran. Elle n'est jamais le seul
 * moyen d'accéder à l'information — la liste textuelle synchronisée du §8.6 est
 * livrée avec les événements, et la recherche de commune reste utilisable sans
 * jamais toucher la carte.
 */

export interface BaseMapProps {
  center?: readonly [number, number];
  zoom?: number;
  /** Restreint le déplacement. Par défaut, la France métropolitaine et la Corse. */
  bounded?: boolean;
  /**
   * `false` : une carte qui se regarde et ne se manipule pas — l'accueil la
   * montre comme une image vivante qui mène à `/carte`. Ni zoom, ni
   * déplacement, ni commandes ; l'attribution IGN reste, elle est due quelle
   * que soit la forme (§9.5).
   */
  interactive?: boolean;
  className?: string;
  /** Événements à afficher. Le premier lot vient du rendu serveur. */
  events?: MapEvent[];
  /**
   * Périmètres à dessiner sous les marqueurs (FR-092). Le style suit la
   * nature : trait plein d'autorité pour l'officiel, tireté pour le reste —
   * un périmètre satellitaire ne ressemble jamais à un contour opérationnel
   * (FR-093).
   */
  perimeters?: PerimeterShape[];
  /** Recharge les événements lorsque l'emprise change. FR-007. */
  reloadOnMove?: boolean;
  /**
   * Marges occupées par des panneaux posés sur la carte, en pixels.
   *
   * MapLibre place le centre demandé au centre de la zone **moins** ces
   * marges : sans elles, une colonne de lecture de 336 px recouvre le tiers
   * ouest de la carte, et la liste d'événements désigne des marqueurs
   * qu'elle cache elle-même — constaté le 11 septembre 2026.
   */
  padding?: { top?: number; right?: number; bottom?: number; left?: number };
  /**
   * Étendue à faire tenir dans la zone visible au premier cadrage, si elle
   * existe. Elle prime sur `center` : une marge place le centre au bon
   * endroit mais laisse les extrêmes tomber où ils veulent — `fitBounds`
   * est le seul à garantir que tout est visible, panneaux déduits.
   *
   * Le zoom n'augmente jamais au-delà de `zoom` : on ne veut pas qu'un feu
   * isolé fasse basculer une carte de territoire en carte de quartier.
   */
  fitBounds?: readonly [readonly [number, number], readonly [number, number]];
  /**
   * Fenêtre temporelle demandée, en heures — `null` pour tout ce que
   * l'emprise porte. La carte recharge à chaque changement, sans attendre
   * un déplacement (FR-005).
   */
  windowHours?: number | null;
  /**
   * Reçoit les événements du dernier chargement **client**.
   *
   * La carte vient de les demander pour dessiner ses marqueurs : les
   * remonter permet à la liste textuelle de montrer exactement ce que la
   * carte montre (§8.6), sans seconde requête et sans second compte.
   */
  onEventsLoaded?: (events: LoadedEventRow[]) => void;
  /**
   * Instant de référence pour la couleur d'âge des marqueurs, ISO 8601.
   * La relecture temporelle colore par l'âge **à l'instant rejoué** (FR-081) ;
   * absent, l'âge se mesure contre maintenant, comme sur la carte vivante.
   */
  ageReference?: string;
  /**
   * Polluant de la couche air modélisée (§19.1), ou null pour l'éteindre.
   * La couche se glisse sous les lavis et les événements : un contexte,
   * jamais le sujet.
   */
  airPollutant?: string | null;
  /**
   * Reçoit ce que la couche air affiche réellement — l'échéance choisie et
   * la palette lue de l'alias — ou null quand rien ne s'affiche : c'est ce
   * qui permet à la légende de décrire la couche sans recopier ses seuils.
   */
  onAirInfo?: (info: AirTilesInfo | null) => void;
  /**
   * Frame radar à afficher (§19.3), ou null pour éteindre la couche. C'est
   * le panneau qui tient la timeline et le rythme ; la carte ne fait
   * qu'afficher la frame qu'on lui donne.
   */
  radarFrame?: RadarFrameDisplay | null;
}

/**
 * MapLibre exige les quatre côtés ; l'appelant ne déclare que ceux qui
 * portent un panneau.
 */
function fullPadding(padding: { top?: number; right?: number; bottom?: number; left?: number }): {
  top: number;
  right: number;
  bottom: number;
  left: number;
} {
  return {
    top: padding.top ?? 0,
    right: padding.right ?? 0,
    bottom: padding.bottom ?? 0,
    left: padding.left ?? 0,
  };
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * L'emprise **réellement visible**, panneaux déduits.
 *
 * `getBounds()` rend celle de toute la toile, y compris le tiers que la
 * colonne de lecture recouvre. Charger là-dessus revient à demander des
 * événements qu'on ne montrera pas — et à en faire la liste, qui désigne
 * alors des marqueurs cachés derrière elle-même : dix sur dix-neuf au
 * relevé du 11 septembre 2026. La marge de la caméra dit exactement ce que
 * les panneaux mangent ; il suffit de la retrancher.
 *
 * La rotation est désactivée sur cette carte, les deux coins suffisent donc
 * à décrire le rectangle.
 */
function visibleBounds(map: maplibregl.Map): [number, number, number, number] {
  // Les quatre côtés sont typés facultatifs par MapLibre, qui les remplit
  // pourtant toujours : l'absence vaut « aucun panneau de ce côté ».
  const padding = fullPadding(map.getPadding());
  const canvas = map.getCanvas();
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  const southWest = map.unproject([padding.left, height - padding.bottom]);
  const northEast = map.unproject([width - padding.right, padding.top]);

  return [southWest.lng, southWest.lat, northEast.lng, northEast.lat];
}

/**
 * Recharge les événements de l'emprise visible. FR-007.
 *
 * Un échec est silencieux côté carte : les marqueurs déjà affichés restent, ce
 * qui vaut mieux que de les effacer. La liste textuelle rendue par le serveur
 * porte, elle, l'horodatage de son propre chargement.
 */
async function reload(
  map: maplibregl.Map,
  windowHours: number | null,
): Promise<LoadedEventRow[] | null> {
  const bbox = visibleBounds(map)
    .map((value) => value.toFixed(4))
    .join(',');

  // FR-005 : la fenêtre est un filtre **annoncé**, porté par le même
  // paramètre `since` que le catalogue — carte et liste comptent donc la
  // même chose, et l'URL de l'API dit ce qui a été demandé.
  const since =
    windowHours === null
      ? ''
      : `&since=${new Date(Date.now() - windowHours * 3_600_000).toISOString()}`;

  try {
    const response = await fetch(`/api/v1/events?bbox=${bbox}&limit=500${since}`);
    if (!response.ok) return null;

    const payload = (await response.json()) as { data: LoadedEventRow[] };

    updateEventLayer(
      map,
      payload.data.map((event) => ({
        publicId: event.id,
        freshnessStatus: event.freshnessStatus,
        lastDetectedAt: event.lastDetectedAt,
        confidence: event.confidence,
        detectionCount: event.detectionCount,
        location: {
          longitude: event.location.coordinates[0],
          latitude: event.location.coordinates[1],
        },
        nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
      })),
    );
    return payload.data;
  } catch {
    // Emprise trop large ou réseau coupé : on garde l'affichage précédent.
    return null;
  }
}

export default function BaseMap({
  center = DEFAULT_VIEW.center,
  zoom = DEFAULT_VIEW.zoom,
  bounded = true,
  interactive = true,
  className,
  events = [],
  perimeters = [],
  reloadOnMove = false,
  padding,
  fitBounds,
  windowHours = null,
  onEventsLoaded,
  ageReference,
  airPollutant = null,
  onAirInfo,
  radarFrame = null,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const router = useRouter();

  // Le rappel vit dans une ref : sa nouvelle identité à chaque rendu ne doit
  // pas relancer l'effet de la couche air.
  const onAirInfoRef = useRef(onAirInfo);
  useEffect(() => {
    onAirInfoRef.current = onAirInfo;
  }, [onAirInfo]);

  // Même motif pour la fenêtre et son rappel : le gestionnaire `moveend`
  // est posé une fois pour toutes et doit lire la fenêtre **courante**,
  // pas celle qui avait cours à sa pose.
  const windowHoursRef = useRef(windowHours);
  const onEventsLoadedRef = useRef(onEventsLoaded);
  useEffect(() => {
    onEventsLoadedRef.current = onEventsLoaded;
  }, [onEventsLoaded]);

  // « Le style a fini de charger » se mémorise ici : `isStyleLoaded()` peut
  // répondre faux transitoirement bien après l'événement `load` (pendant un
  // chargement de tuiles), et un `once('load')` posé à ce moment-là ne
  // tirerait plus jamais.
  const styleReadyRef = useRef(false);

  // Le premier lot vient du serveur : la liste textuelle est rendue sans
  // JavaScript, et la carte n'attend pas un aller-retour pour montrer quelque
  // chose. Les lots suivants sont chargés à l'emprise.
  //
  // La ref n'est initialisée qu'ici et mise à jour dans un effet : la muter
  // pendant le rendu rendrait le composant non réentrant.
  const eventsRef = useRef<MapEvent[]>(events);
  const perimetersRef = useRef<PerimeterShape[]>(perimeters);
  const ageReferenceRef = useRef(ageReference);

  // Ce que porte la carte au moment où le style change. Un changement de
  // thème remplace le style entier — sources et couches comprises — et il
  // faut tout reposer : ces refs disent quoi, sans redemander au réseau
  // ce qui a déjà été résolu.
  const tilesUrlRef = useRef<string | null>(null);
  const airInfoRef = useRef<AirTilesInfo | null>(null);
  const radarFrameRef = useRef<RadarFrameDisplay | null>(radarFrame);

  // Les gestionnaires d'événements, eux, se posent **une fois**. Ils sont
  // attachés à un identifiant de couche, pas à une couche : ils survivent
  // au remplacement du style, et les reposer à chaque fois ferait ouvrir
  // la fiche autant de fois que le thème a été basculé.
  const handlersWiredRef = useRef(false);

  // Initialisation unique. Les changements de cadrage passent par l'effet
  // suivant : recréer la carte à chaque navigation rechargerait toutes les
  // tuiles pour rien.
  useEffect(() => {
    const container = containerRef.current;
    if (container === null || mapRef.current !== null) return;

    registerPmtilesProtocol();

    let unsubscribeTheme: (() => void) | null = null;

    // `exactOptionalPropertyTypes` interdit de passer `maxBounds: undefined` :
    // la propriété est ajoutée seulement lorsqu'elle a une valeur.
    const boundsOption = bounded
      ? {
          maxBounds: [
            [DEFAULT_VIEW.maxBounds[0][0], DEFAULT_VIEW.maxBounds[0][1]],
            [DEFAULT_VIEW.maxBounds[1][0], DEFAULT_VIEW.maxBounds[1][1]],
          ] satisfies [[number, number], [number, number]],
        }
      : {};

    // Le style n'est **pas** posé par le constructeur : il l'est juste
    // après, par `applyBasemapStyle`. C'est le seul chemin qui accepte
    // `transformStyle`, par où passe la dérivation sombre — voir
    // `lib/map/basemap-style.ts`. Le constructeur ferait sinon une
    // première requête pour un fond clair aussitôt remplacé.
    const map = new maplibregl.Map({
      container,
      center: [center[0], center[1]],
      zoom,
      interactive,
      ...boundsOption,
      // L'attribution IGN est obligatoire et ne doit pas être repliée (§9.5).
      //
      // `customAttribution` n'est pas une ceinture de sécurité : c'est la
      // seule attribution servie. Le style **vectoriel** de la Géoplateforme
      // ne déclare pas d'attribution sur ses sources, si bien que le contrôle
      // restait vide (`maplibregl-attrib-empty`, 0 × 0) — constaté le
      // 11 septembre 2026. Le test de `map-style` couvrait le style raster,
      // qui la porte bien, mais c'est le vectoriel qui est affiché : une
      // porte verte sur le chemin qu'on n'emprunte pas.
      attributionControl: { compact: false, customAttribution: IGN_ATTRIBUTION },
      // Le relief incliné n'apporte rien à la lecture d'une détection et
      // complique la comparaison des distances.
      pitchWithRotate: false,
      dragRotate: false,
      // Le sprite de la Géoplateforme n'existe qu'en simple densité ;
      // MapLibre en demande une version `@2x` dès que l'écran a plus d'un
      // pixel physique par pixel CSS, et reçoit un 404. Le sprite entier
      // manquait alors — donc tous les motifs de surface. Constaté le
      // 11 septembre 2026, antérieur au thème sombre.
      transformRequest: (url, resourceType) =>
        resourceType === 'SpriteImage' || resourceType === 'SpriteJSON'
          ? { url: withoutRetinaSprite(url) }
          : undefined,
    });

    // Avant tout cadrage : la marge fait partie de la caméra, pas d'un
    // ajustement d'après-coup qui ferait sauter la carte au montage.
    if (padding !== undefined) map.setPadding(fullPadding(padding));

    // L'étendue prime sur le centre quand elle est donnée. `duration: 0` :
    // au montage, il n'y a rien à animer depuis, et une animation d'ouverture
    // sur une carte de feux est un ornement.
    if (fitBounds !== undefined) {
      map.fitBounds(
        [
          [fitBounds[0][0], fitBounds[0][1]],
          [fitBounds[1][0], fitBounds[1][1]],
        ],
        {
          ...(padding === undefined ? {} : { padding: fullPadding(padding) }),
          maxZoom: zoom,
          duration: 0,
        },
      );
    }

    // Une carte qui ne se manipule pas n'a pas de commandes à montrer ; le
    // curseur dit qu'elle mène quelque part.
    if (interactive) {
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
    } else {
      map.getCanvas().style.cursor = 'pointer';
    }

    /**
     * Pose les calques de MapFeux sur le style courant.
     *
     * Appelée à chaque `style.load` : au premier chargement, et de nouveau
     * après chaque bascule de thème, puisque `setStyle` remplace le style
     * entier — sources et couches ajoutées comprises.
     */
    const buildLayers = (): void => {
      // Les périmètres avant les événements : le contour encadre, les
      // détections restent au premier plan.
      if (perimetersRef.current.length > 0) {
        addPerimeterLayer(map, perimetersRef.current);
      }

      const reference = ageReferenceRef.current;
      addEventLayer(
        map,
        eventsRef.current,
        reference === undefined ? undefined : new Date(reference),
      );

      const placeDepartments = (tilesUrl: string): void => {
        addDepartmentLayer(map, tilesUrl);
        // Sous les événements : chaque couche d'événements repasse au-dessus,
        // dans son ordre d'origine — traîne, lueur, halo, disque.
        for (const layerId of [
          EVENTS_TAIL_LAYER_ID,
          EVENTS_GLOW_LAYER_ID,
          EVENTS_HALO_LAYER_ID,
          EVENTS_CIRCLE_LAYER_ID,
        ]) {
          if (map.getLayer(layerId) !== undefined) {
            map.moveLayer(layerId);
          }
        }
        void loadDepartmentAggregates(map);
      };

      // L'alias des tuiles n'est résolu qu'une fois : une bascule de thème
      // repose les calques, elle ne redemande pas au réseau ce qu'il a déjà
      // répondu.
      if (tilesUrlRef.current !== null) {
        placeDepartments(tilesUrlRef.current);
      } else {
        void resolveTilesUrl().then((tilesUrl) => {
          if (tilesUrl === null || mapRef.current === null) return;
          tilesUrlRef.current = tilesUrl;
          placeDepartments(tilesUrl);
        });
      }

      // Les calques appelés se reposent tels qu'ils étaient : ni l'archive
      // d'air ni la frame radar ne sont redemandées, seule leur couche est
      // reconstruite — elles s'insèrent d'elles-mêmes sous les événements.
      if (airInfoRef.current !== null) setAirLayer(map, airInfoRef.current);
      if (radarFrameRef.current !== null) setRadarFrame(map, radarFrameRef.current);
    };

    /**
     * Gestionnaires posés une seule fois, pour la vie de la carte.
     *
     * MapLibre les attache à un **identifiant** de couche : ils survivent
     * donc au remplacement du style, et les reposer à chaque bascule
     * ouvrirait la fiche autant de fois que le thème a changé.
     */
    const wireHandlers = (): void => {
      // Un clic sur un département ouvert mène à sa page ; un département
      // « à venir » n'est pas cliquable — pas de page à promettre (FR-015).
      map.on('click', DEPARTMENTS_FILL_LAYER_ID, (event) => {
        if (map.getZoom() >= 9) return;
        const properties = event.features?.[0]?.properties ?? {};
        const statut = properties['statut'];
        const slug = properties['slug'];
        if ((statut === 'pilot' || statut === 'active') && typeof slug === 'string') {
          router.push(`/territoires/${slug}`);
        }
      });
      map.on('mousemove', DEPARTMENTS_FILL_LAYER_ID, (event) => {
        if (map.getZoom() >= 9) return;
        const statut = event.features?.[0]?.properties?.['statut'];
        map.getCanvas().style.cursor = statut === 'pilot' || statut === 'active' ? 'pointer' : '';
      });
      map.on('mouseleave', DEPARTMENTS_FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = '';
      });

      // Un clic ouvre la fiche : la carte oriente vers l'événement, elle ne
      // prétend pas le décrire. Toute l'information sourcée est sur la fiche.
      //
      // La traîne est cliquable au même titre que le reste : elle est rendue
      // discrète, pas inaccessible.
      for (const layerId of CLICKABLE_LAYER_IDS) {
        map.on('click', layerId, (event) => {
          const publicId = event.features?.[0]?.properties?.['publicId'];
          if (typeof publicId === 'string') {
            router.push(`/evenements/${publicId}`);
          }
        });

        map.on('mouseenter', layerId, () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
        });
      }

      if (reloadOnMove) {
        map.on('moveend', () => {
          void reload(map, windowHoursRef.current).then((loaded) => {
            if (loaded !== null) onEventsLoadedRef.current?.(loaded);
          });
        });
      }
    };

    // `style.load` et non `load` : le premier retire à chaque style, le
    // second une seule fois dans la vie de la carte. C'est la même pose de
    // calques qu'il faut rejouer après une bascule de thème.
    map.on('style.load', () => {
      styleReadyRef.current = true;
      buildLayers();
      if (!handlersWiredRef.current) {
        handlersWiredRef.current = true;
        wireHandlers();
      }
    });

    mapRef.current = map;
    // Poignée de débogage, développement seulement : dans un panneau de
    // navigation sans compositing, `requestAnimationFrame` ne tire jamais et
    // la carte ne « charge » pas — c'est par cette poignée qu'on la pilote.
    if (process.env.NODE_ENV === 'development') {
      (window as unknown as { __mapfeuxMap?: maplibregl.Map }).__mapfeuxMap = map;
    }

    // Le fond, enfin : `style.load` est déjà branché, il posera les calques
    // dès que la feuille sera là — au premier chargement comme après une
    // bascule de thème.
    let dark = isDarkTheme();
    applyBasemapStyle(map, dark);

    unsubscribeTheme = subscribeTheme(() => {
      const next = isDarkTheme();
      if (next === dark) return;
      dark = next;
      applyBasemapStyle(map, next);
    });

    return () => {
      unsubscribeTheme?.();
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // Volontairement sans dépendances : la carte se crée une fois.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mise à jour de la couche lorsque le serveur fournit un nouveau lot.
  useEffect(() => {
    eventsRef.current = events;
    ageReferenceRef.current = ageReference;
    const map = mapRef.current;
    if (map !== null && map.isStyleLoaded()) {
      updateEventLayer(
        map,
        events,
        ageReference === undefined ? undefined : new Date(ageReference),
      );
    }
  }, [events, ageReference]);

  useEffect(() => {
    perimetersRef.current = perimeters;
    const map = mapRef.current;
    if (map !== null && map.isStyleLoaded()) {
      updatePerimeterLayer(map, perimeters);
    }
  }, [perimeters]);

  // Couche air modélisée (§19.1). L'alias est relu à chaque activation :
  // c'est lui qui dit quelle archive est courante, et c'est court.
  useEffect(() => {
    const map = mapRef.current;
    if (map === null) return;
    let cancelled = false;

    const apply = async (): Promise<void> => {
      if (airPollutant === null) {
        airInfoRef.current = null;
        removeAirLayer(map);
        onAirInfoRef.current?.(null);
        return;
      }
      const info = await resolveAirTiles(airPollutant);
      if (cancelled || mapRef.current === null) return;
      // Mémorisée pour la reposer après une bascule de thème, qui remplace
      // le style et emporte la couche avec lui.
      airInfoRef.current = info;
      if (info === null) {
        removeAirLayer(map);
      } else {
        setAirLayer(map, info);
      }
      onAirInfoRef.current?.(info);
    };

    if (styleReadyRef.current) {
      void apply();
    } else {
      map.once('load', () => void apply());
    }
    return () => {
      cancelled = true;
    };
  }, [airPollutant]);

  // Changement de fenêtre : rechargement immédiat, sans attendre un
  // déplacement. Le premier rendu vient du serveur avec la même fenêtre —
  // le montage ne recharge donc rien, il n'y aurait qu'un aller-retour pour
  // le même résultat.
  const windowSettledRef = useRef(false);
  useEffect(() => {
    windowHoursRef.current = windowHours;
    const map = mapRef.current;
    if (map === null) return;
    if (!windowSettledRef.current) {
      windowSettledRef.current = true;
      return;
    }
    const run = (): void => {
      void reload(map, windowHours).then((loaded) => {
        if (loaded !== null) onEventsLoadedRef.current?.(loaded);
      });
    };
    if (styleReadyRef.current) {
      run();
    } else {
      map.once('load', run);
    }
  }, [windowHours]);

  // Couche radar (§19.3). Changer de frame ne touche que l'image de la
  // source : c'est ce qui rend l'animation fluide.
  useEffect(() => {
    radarFrameRef.current = radarFrame;
    const map = mapRef.current;
    if (map === null) return;

    const apply = (): void => {
      if (mapRef.current === null) return;
      if (radarFrame === null) {
        removeRadarLayer(map);
      } else {
        setRadarFrame(map, radarFrame);
      }
    };

    if (styleReadyRef.current) {
      apply();
    } else {
      map.once('load', apply);
    }
  }, [radarFrame]);

  // La marge suit la mise en page : les panneaux ne flottent qu'au-dessus de
  // 640 px, en dessous ils s'empilent et ne couvrent plus rien.
  useEffect(() => {
    const map = mapRef.current;
    if (map === null || padding === undefined) return;
    map.setPadding(fullPadding(padding));
  }, [padding]);

  // Recadrage lorsque le territoire consulté change.
  useEffect(() => {
    const map = mapRef.current;
    if (map === null) return;

    if (prefersReducedMotion()) {
      map.jumpTo({ center: [center[0], center[1]], zoom });
    } else {
      map.flyTo({ center: [center[0], center[1]], zoom, duration: 800 });
    }
  }, [center, zoom]);

  return (
    <div
      ref={containerRef}
      className={className}
      // Le canevas est focusable par MapLibre ; ce libellé annonce ce qu'il est.
      role="application"
      aria-label="Carte des détections thermiques"
    />
  );
}
