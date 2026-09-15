import 'server-only';

import type {
  ConfidenceLevel,
  EventFreshness,
  OfficialControlStatus,
  Provenance,
  TimelineEntryType,
  VerificationStatus,
} from '@mapfeux/domain';

import { createPublicReadClient } from '@/lib/supabase/server';

import { readable, unreadable, type ReadResult } from './read-result';

/**
 * Accès aux événements.
 *
 * Référence : cahier §5.6 et §5.7.
 *
 * La fiche doit être rendue côté serveur et rester lisible sans JavaScript
 * (FR-051). Tout ce qu'elle affiche est donc chargé ici, en trois requêtes au
 * plus, avant le premier octet envoyé au navigateur.
 *
 * Chaque lecture rend un `ReadResult` : une base qui ne répond pas n'est ni
 * une liste vide ni un événement introuvable, et l'appelant — page ou route —
 * doit le dire (`lib/data/read-result.ts`).
 */

interface EventRow {
  public_id: string;
  freshness_status: EventFreshness;
  verification_status: VerificationStatus;
  official_control_status: OfficialControlStatus | null;
  official_status_at: string | null;
  official_organisation: string | null;
  official_source_url: string | null;
  first_detected_at: string;
  last_detected_at: string;
  longitude: number;
  latitude: number;
  detection_count: number;
  sensor_count: number;
  sensors: string[];
  satellites: string[];
  confidence_level: ConfidenceLevel;
  frp_min_mw: number | null;
  frp_median_mw: number | null;
  frp_max_mw: number | null;
  nearest_municipality_code: string | null;
  nearest_municipality_name: string | null;
  territory_slug: string | null;
  territory_name: string | null;
  territory_timezone: string;
  last_public_snapshot_at: string | null;
  updated_at: string;
  timeline_entry_count: number;
  timeline_latest_at: string | null;
  editorial_slug: string | null;
}

export interface FireEvent {
  publicId: string;
  freshnessStatus: EventFreshness;
  verificationStatus: VerificationStatus;
  officialControlStatus: OfficialControlStatus | null;
  /** Attribution de l'information officielle. Absente si aucun statut officiel. */
  officialSource: { organisation: string; url: string | null; publishedAt: string } | null;
  firstDetectedAt: Date;
  lastDetectedAt: Date;
  location: { longitude: number; latitude: number };
  detectionCount: number;
  sensorCount: number;
  sensors: string[];
  satellites: string[];
  confidenceLevel: ConfidenceLevel;
  frp: { min: number | null; median: number | null; max: number | null };
  nearestMunicipality: { insee: string; name: string } | null;
  territory: { slug: string; name: string } | null;
  timeZone: string;
  lastSnapshotAt: Date | null;
  updatedAt: Date;
  timelineEntryCount: number;
  timelineLatestAt: Date | null;
  /** Slug éditorial facultatif (FR-042). Posé par un humain, jamais généré. */
  editorialSlug: string | null;
}

/**
 * Chemin canonique d'une fiche : l'identifiant, plus le slug éditorial quand
 * un humain en a posé un (FR-060). L'URL nue reste servie quoi qu'il arrive —
 * le slug s'ajoute, il ne remplace pas.
 */
export function eventPath(event: Pick<FireEvent, 'publicId' | 'editorialSlug'>): string {
  return event.editorialSlug === null
    ? `/evenements/${event.publicId}`
    : `/evenements/${event.publicId}/${event.editorialSlug}`;
}

export interface TimelineEntry {
  id: string;
  entryType: TimelineEntryType;
  provenance: Provenance;
  occurredAt: Date;
  recordedAt: Date;
  title: string;
  summary: string | null;
  source: { organisation: string; url: string } | null;
}

export interface EventDetection {
  acquiredAt: Date;
  sensor: string;
  satellite: string;
  location: { longitude: number; latitude: number };
  confidenceLevel: 'low' | 'medium' | 'high' | 'unknown';
  frpMw: number | null;
  dayNight: string | null;
  isKnownThermalSource: boolean;
}

function toEvent(row: EventRow): FireEvent {
  return {
    publicId: row.public_id,
    freshnessStatus: row.freshness_status,
    verificationStatus: row.verification_status,
    officialControlStatus: row.official_control_status,
    officialSource:
      row.official_organisation === null || row.official_status_at === null
        ? null
        : {
            organisation: row.official_organisation,
            url: row.official_source_url,
            publishedAt: row.official_status_at,
          },
    firstDetectedAt: new Date(row.first_detected_at),
    lastDetectedAt: new Date(row.last_detected_at),
    location: { longitude: row.longitude, latitude: row.latitude },
    detectionCount: row.detection_count,
    sensorCount: row.sensor_count,
    sensors: row.sensors,
    satellites: row.satellites,
    confidenceLevel: row.confidence_level,
    frp: {
      min: row.frp_min_mw === null ? null : Number(row.frp_min_mw),
      median: row.frp_median_mw === null ? null : Number(row.frp_median_mw),
      max: row.frp_max_mw === null ? null : Number(row.frp_max_mw),
    },
    nearestMunicipality:
      row.nearest_municipality_code === null || row.nearest_municipality_name === null
        ? null
        : { insee: row.nearest_municipality_code, name: row.nearest_municipality_name },
    territory:
      row.territory_slug === null || row.territory_name === null
        ? null
        : { slug: row.territory_slug, name: row.territory_name },
    timeZone: row.territory_timezone,
    lastSnapshotAt:
      row.last_public_snapshot_at === null ? null : new Date(row.last_public_snapshot_at),
    updatedAt: new Date(row.updated_at),
    timelineEntryCount: row.timeline_entry_count,
    timelineLatestAt: row.timeline_latest_at === null ? null : new Date(row.timeline_latest_at),
    editorialSlug: row.editorial_slug,
  };
}

/**
 * `null` si l'événement n'existe pas ou a été masqué ; `readable: false` si
 * la base n'a pas répondu. L'appelant ne doit pas prendre l'un pour l'autre :
 * un 404 rendu sur une panne ferait périmer une URL qui existe (§13.10).
 *
 * Le masquage est traité en base : un événement retiré du public l'est aussi
 * par son URL directe (§17.7).
 */
export async function fetchEvent(publicId: string): Promise<ReadResult<FireEvent | null>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event', { event_public_id: publicId });

  if (error !== null) {
    console.error('[events] lecture impossible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  const rows = (data ?? []) as EventRow[];
  const first = rows[0];
  return readable(first === undefined ? null : toEvent(first));
}

/**
 * Résout un identifiant fusionné vers l'événement canonique.
 * `null` si l'identifiant n'est connu ni comme événement, ni comme alias —
 * permet à l'appelant de distinguer une redirection d'un 404 (§13.10).
 */
export async function resolveEventAlias(candidate: string): Promise<ReadResult<string | null>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('resolve_event_alias', {
    candidate_public_id: candidate,
  });

  if (error !== null) {
    console.error('[events] résolution d’alias impossible', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  return readable((data as string | null) ?? null);
}

/**
 * Ce qu'un identifiant public désigne : un événement publié, un alias
 * fusionné vers un autre identifiant, ou rien. Les trois réponses se
 * traitent différemment — servir, rediriger, 404 — et aucune ne se déduit
 * d'une base qui n'a pas répondu.
 */
export type EventLookup =
  | { readonly kind: 'event'; readonly event: FireEvent }
  | { readonly kind: 'alias'; readonly canonical: string }
  | { readonly kind: 'missing' };

export async function lookupEvent(publicId: string): Promise<ReadResult<EventLookup>> {
  const event = await fetchEvent(publicId);
  if (!event.readable) return unreadable();
  if (event.value !== null) return readable({ kind: 'event', event: event.value });

  const canonical = await resolveEventAlias(publicId);
  if (!canonical.readable) return unreadable();
  if (canonical.value !== null && canonical.value !== publicId) {
    return readable({ kind: 'alias', canonical: canonical.value });
  }
  return readable({ kind: 'missing' });
}

export async function fetchEventTimeline(publicId: string): Promise<ReadResult<TimelineEntry[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_timeline', {
    event_public_id: publicId,
  });

  if (error !== null) {
    console.error('[events] chronologie illisible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    id: string;
    entry_type: TimelineEntryType;
    provenance: Provenance;
    occurred_at: string;
    recorded_at: string;
    title: string;
    summary: string | null;
    source_organisation: string | null;
    source_url: string | null;
  };

  return readable(
    ((data ?? []) as Row[]).map((row) => ({
      id: row.id,
      entryType: row.entry_type,
      provenance: row.provenance,
      occurredAt: new Date(row.occurred_at),
      recordedAt: new Date(row.recorded_at),
      title: row.title,
      summary: row.summary,
      source:
        row.source_organisation === null || row.source_url === null
          ? null
          : { organisation: row.source_organisation, url: row.source_url },
    })),
  );
}

/**
 * Vue de la fiche, snapshot d'abord.
 *
 * Référence : cahier §21.5 et FR-052.
 *
 * L'origine est retournée au lieu d'être masquée : la page doit pouvoir dire
 * qu'elle affiche un état figé, et depuis quand. Un repli silencieux sur le
 * cache présenté comme actuel est exactement ce que le §21.5 interdit.
 */
export interface EventView {
  readonly origin: 'snapshot' | 'live';
  /** Heure de construction du snapshot. Nulle en lecture directe. */
  readonly generatedAt: Date | null;
  readonly event: FireEvent;
  /**
   * Toujours lue dans un snapshot ; en lecture directe, sa propre lecture
   * peut manquer alors que l'événement, lui, a été lu — la fiche le dit à
   * l'endroit de la chronologie, pas à la place de la fiche.
   */
  readonly timeline: ReadResult<TimelineEntry[]>;
}

interface SnapshotPayload {
  id: string;
  /** Absent des snapshots antérieurs au 25 août 2026 : lu avec repli nul. */
  editorialSlug?: string | null;
  freshnessStatus: EventFreshness;
  verificationStatus: VerificationStatus;
  officialControlStatus: OfficialControlStatus | null;
  officialStatusSource: { organisation: string; url: string | null; publishedAt: string } | null;
  firstDetectedAt: string;
  lastDetectedAt: string;
  location: { longitude: number; latitude: number };
  detectionCount: number;
  sensorCount: number;
  sensors: string[];
  satellites: string[];
  confidence: ConfidenceLevel;
  frpMw: { min: number | null; median: number | null; max: number | null };
  nearestMunicipality: { insee: string; name: string } | null;
  territory: { slug: string; name: string } | null;
  timeZone: string;
  timeline: {
    id: string;
    entryType: TimelineEntryType;
    provenance: Provenance;
    occurredAt: string;
    recordedAt: string;
    title: string;
    summary: string | null;
    source: { organisation: string; url: string } | null;
  }[];
  updatedAt: string;
}

export async function fetchEventView(publicId: string): Promise<ReadResult<EventView | null>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_snapshot', {
    event_public_id: publicId,
  });

  if (error === null) {
    const rows = (data ?? []) as {
      generated_at: string;
      data_at: string;
      payload: SnapshotPayload;
    }[];
    const snapshot = rows[0];

    if (snapshot !== undefined) {
      const p = snapshot.payload;
      return readable({
        origin: 'snapshot',
        generatedAt: new Date(snapshot.generated_at),
        event: {
          publicId: p.id,
          editorialSlug: p.editorialSlug ?? null,
          freshnessStatus: p.freshnessStatus,
          verificationStatus: p.verificationStatus,
          officialControlStatus: p.officialControlStatus,
          officialSource: p.officialStatusSource,
          firstDetectedAt: new Date(p.firstDetectedAt),
          lastDetectedAt: new Date(p.lastDetectedAt),
          location: p.location,
          detectionCount: p.detectionCount,
          sensorCount: p.sensorCount,
          sensors: p.sensors,
          satellites: p.satellites,
          confidenceLevel: p.confidence,
          frp: p.frpMw,
          nearestMunicipality: p.nearestMunicipality,
          territory: p.territory,
          timeZone: p.timeZone,
          lastSnapshotAt: new Date(snapshot.generated_at),
          updatedAt: new Date(p.updatedAt),
          timelineEntryCount: p.timeline.length,
          timelineLatestAt: p.timeline[0] === undefined ? null : new Date(p.timeline[0].occurredAt),
        },
        timeline: readable(
          p.timeline.map((entry) => ({
            id: entry.id,
            entryType: entry.entryType,
            provenance: entry.provenance,
            occurredAt: new Date(entry.occurredAt),
            recordedAt: new Date(entry.recordedAt),
            title: entry.title,
            summary: entry.summary,
            source: entry.source,
          })),
        ),
      });
    }
  } else {
    console.error('[events] snapshot illisible, repli sur la lecture directe', {
      publicId,
      code: error.code,
      message: error.message,
    });
  }

  // Aucun snapshot : événement trop récent pour en avoir un, ou tâche de
  // rafraîchissement en retard. La lecture directe reste correcte, elle est
  // seulement plus coûteuse. Snapshot illisible **et** lecture directe
  // illisible : c'est la base qui ne répond pas, et la fiche doit le dire
  // plutôt que de se déclarer introuvable.
  const event = await fetchEvent(publicId);
  if (!event.readable) return unreadable();
  if (event.value === null) return readable(null);

  return readable({
    origin: 'live',
    generatedAt: null,
    event: event.value,
    timeline: await fetchEventTimeline(event.value.publicId),
  });
}

/** Résumé d'événement pour la carte et la liste textuelle. */
export interface EventSummary {
  publicId: string;
  freshnessStatus: EventFreshness;
  verificationStatus: VerificationStatus;
  officialControlStatus: OfficialControlStatus | null;
  firstDetectedAt: Date;
  lastDetectedAt: Date;
  location: { longitude: number; latitude: number };
  detectionCount: number;
  confidenceLevel: ConfidenceLevel;
  nearestMunicipality: { insee: string; name: string } | null;
}

export interface BoundingBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

/**
 * Curseur du catalogue : (dernière observation, identifiant public), encodé
 * base64url. Opaque pour le consommateur, mais décodable — il ne transporte
 * donc que des valeurs déjà publiques (§15.1), jamais l'identifiant interne.
 */
export interface CatalogCursor {
  lastDetectedAt: Date;
  publicId: string;
}

export function encodeCatalogCursor(cursor: CatalogCursor): string {
  return Buffer.from(`${cursor.lastDetectedAt.toISOString()}|${cursor.publicId}`, 'utf8').toString(
    'base64url',
  );
}

const PUBLIC_ID_IN_CURSOR = /^[A-Z0-9-]{4,32}$/;

/** Rend `null` si le curseur est illisible — l'appelant décide de la suite. */
export function decodeCatalogCursor(raw: string): CatalogCursor | null {
  try {
    const decoded = Buffer.from(raw, 'base64url').toString('utf8');
    const [iso, publicId] = decoded.split('|');
    if (iso === undefined || publicId === undefined) return null;
    const lastDetectedAt = new Date(iso);
    if (Number.isNaN(lastDetectedAt.getTime())) return null;
    if (!PUBLIC_ID_IN_CURSOR.test(publicId)) return null;
    return { lastDetectedAt, publicId };
  } catch {
    return null;
  }
}

export interface CatalogFilters {
  since?: Date;
  until?: Date;
  department?: string;
  verification?: string;
  /** Fraîcheur technique exacte — `archived` porte la page /archives (FR-053). */
  freshness?: string;
  cursor?: CatalogCursor;
  limit?: number;
}

/**
 * Catalogue national, trié par dernière observation (FR-052), sans emprise :
 * la borne est la pagination par jeu de clés, pas une bbox. FR-050 à FR-055.
 */
export async function fetchEventsCatalog(
  filters: CatalogFilters = {},
): Promise<ReadResult<{ events: EventSummary[]; nextCursor: string | null }>> {
  const supabase = createPublicReadClient();
  const limit = Math.min(Math.max(filters.limit ?? 50, 1), 100);

  const { data, error } = await supabase.rpc('events_catalog', {
    since: filters.since?.toISOString() ?? null,
    until_at: filters.until?.toISOString() ?? null,
    department: filters.department ?? null,
    verification: filters.verification ?? null,
    freshness: filters.freshness ?? null,
    cursor_last: filters.cursor?.lastDetectedAt.toISOString() ?? null,
    cursor_public: filters.cursor?.publicId ?? null,
    max_results: limit,
  });

  if (error !== null) {
    // Pas une première page vide : la route répondrait 200 et le CDN garderait
    // ce faux vide une minute. La panne se dit.
    console.error('[events] catalogue indisponible', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    public_id: string;
    freshness_status: EventFreshness;
    verification_status: VerificationStatus;
    official_control_status: OfficialControlStatus | null;
    first_detected_at: string;
    last_detected_at: string;
    longitude: number;
    latitude: number;
    detection_count: number;
    confidence_level: ConfidenceLevel;
    nearest_municipality_code: string | null;
    nearest_municipality_name: string | null;
  };

  const events = ((data ?? []) as Row[]).map((row) => ({
    publicId: row.public_id,
    freshnessStatus: row.freshness_status,
    verificationStatus: row.verification_status,
    officialControlStatus: row.official_control_status,
    firstDetectedAt: new Date(row.first_detected_at),
    lastDetectedAt: new Date(row.last_detected_at),
    location: { longitude: row.longitude, latitude: row.latitude },
    detectionCount: row.detection_count,
    confidenceLevel: row.confidence_level,
    nearestMunicipality:
      row.nearest_municipality_code === null || row.nearest_municipality_name === null
        ? null
        : { insee: row.nearest_municipality_code, name: row.nearest_municipality_name },
  }));

  const lastRow = events[events.length - 1];
  const nextCursor =
    events.length === limit && lastRow !== undefined
      ? encodeCatalogCursor({
          lastDetectedAt: lastRow.lastDetectedAt,
          publicId: lastRow.publicId,
        })
      : null;

  return readable({ events, nextCursor });
}

export interface DepartmentAggregateRow {
  departmentCode: string;
  departmentSlug: string;
  departmentStatus: string;
  /**
   * Nom et destination du département, publiés avec le compte : le registre
   * public des territoires ne dit rien des départements « à venir »
   * (FR-014), et la carte nationale doit pouvoir nommer et rejoindre les
   * quatre-vingt-seize.
   */
  departmentName: string | null;
  center: { longitude: number; latitude: number } | null;
  defaultZoom: number | null;
  events: number;
  substantiated: number;
  lastDetectedAt: Date;
}

/**
 * Comptes d'événements visibles par département. FR-003 et §21.2.
 *
 * L'agrégat est calculé en base depuis la même vue que la carte : ce que la
 * vue masque, l'agrégat l'ignore par construction. Un département absent du
 * résultat n'a simplement aucun événement sur la période — quand la base a
 * répondu ; sinon, l'accueil additionnait des lignes absentes et affichait
 * « 0 événement » sur une panne.
 */
export async function fetchDepartmentAggregates(
  since: Date,
): Promise<ReadResult<DepartmentAggregateRow[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('department_event_aggregates', {
    since: since.toISOString(),
  });

  if (error !== null) {
    console.error('[events] agrégats départementaux indisponibles', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    department_code: string;
    department_slug: string;
    department_status: string;
    department_name: string | null;
    center_longitude: number | string | null;
    center_latitude: number | string | null;
    default_zoom: number | string | null;
    events: number;
    substantiated: number;
    last_detected_at: string;
  };

  // `numeric` et `double precision` peuvent arriver en chaîne par PostgREST :
  // on lit des nombres, ou rien.
  const toNumber = (value: number | string | null): number | null => {
    if (value === null) return null;
    const parsed = typeof value === 'number' ? value : Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  return readable(
    ((data ?? []) as Row[]).map((row) => {
      const longitude = toNumber(row.center_longitude);
      const latitude = toNumber(row.center_latitude);
      return {
        departmentCode: row.department_code,
        departmentSlug: row.department_slug,
        departmentStatus: row.department_status,
        departmentName: row.department_name ?? null,
        center: longitude === null || latitude === null ? null : { longitude, latitude },
        defaultZoom: toNumber(row.default_zoom),
        events: row.events,
        substantiated: row.substantiated,
        lastDetectedAt: new Date(row.last_detected_at),
      };
    }),
  );
}

/**
 * Événements d'une emprise. Cahier FR-007 et §15.4.
 *
 * L'emprise est obligatoire : servir la France entière en un appel irait contre
 * la règle « ne charger que les données nécessaires à l'emprise visible », et
 * deviendrait intenable dès qu'une saison chargée aura rempli la base.
 */
export async function fetchEventsInBbox(
  bbox: BoundingBox,
  options: { since?: Date; limit?: number } = {},
): Promise<ReadResult<EventSummary[]>> {
  const supabase = createPublicReadClient();
  // La fonction SQL garde son nom historique : la renommer passe par une
  // migration, sans bénéfice public — seul le nom exposé par l'URL compte.
  const { data, error } = await supabase.rpc('fires_in_bbox', {
    min_lon: bbox.minLon,
    min_lat: bbox.minLat,
    max_lon: bbox.maxLon,
    max_lat: bbox.maxLat,
    since: options.since?.toISOString() ?? null,
    max_results: options.limit ?? 200,
  });

  if (error !== null) {
    console.error('[events] lecture par emprise impossible', {
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    public_id: string;
    freshness_status: EventFreshness;
    verification_status: VerificationStatus;
    official_control_status: OfficialControlStatus | null;
    first_detected_at: string;
    last_detected_at: string;
    longitude: number;
    latitude: number;
    detection_count: number;
    confidence_level: ConfidenceLevel;
    nearest_municipality_code: string | null;
    nearest_municipality_name: string | null;
  };

  return readable(
    ((data ?? []) as Row[]).map((row) => ({
      publicId: row.public_id,
      freshnessStatus: row.freshness_status,
      verificationStatus: row.verification_status,
      officialControlStatus: row.official_control_status,
      firstDetectedAt: new Date(row.first_detected_at),
      lastDetectedAt: new Date(row.last_detected_at),
      location: { longitude: row.longitude, latitude: row.latitude },
      detectionCount: row.detection_count,
      confidenceLevel: row.confidence_level,
      nearestMunicipality:
        row.nearest_municipality_code === null || row.nearest_municipality_name === null
          ? null
          : { insee: row.nearest_municipality_code, name: row.nearest_municipality_name },
    })),
  );
}

/** Une version de périmètre, telle que la fiche et la relecture la jugent. */
export interface EventPerimeter {
  id: string;
  perimeterType: string;
  validAt: Date;
  publishedAt: Date | null;
  importedAt: Date;
  areaHa: number;
  sourceAreaHa: number | null;
  resolutionM: number | null;
  confidenceLevel: string;
  method: string;
  sourceName: string;
  sourceAttribution: string | null;
  isCurrent: boolean;
  supersedesId: string | null;
  /** GeoJSON MultiPolygon, prêt pour la carte. */
  geometry: GeoJSON.MultiPolygon;
  /** L'instant où la version est devenue connaissable — publication source,
   *  à défaut import : c'est lui que la relecture rejoue (FR-094). */
  knownAt: Date;
}

export async function fetchEventPerimeters(
  publicId: string,
): Promise<ReadResult<EventPerimeter[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_perimeters', {
    event_public_id: publicId,
  });

  if (error !== null) {
    console.error('[events] périmètres illisibles', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    id: string;
    perimeter_type: string;
    valid_at: string;
    published_at: string | null;
    imported_at: string;
    area_ha: number;
    source_area_ha: number | null;
    resolution_m: number | null;
    confidence_level: string;
    method: string;
    source_name: string;
    source_attribution: string | null;
    is_current: boolean;
    supersedes_id: string | null;
    geometry: GeoJSON.MultiPolygon;
  };

  return readable(
    ((data ?? []) as Row[]).map((row) => ({
      id: row.id,
      perimeterType: row.perimeter_type,
      validAt: new Date(row.valid_at),
      publishedAt: row.published_at === null ? null : new Date(row.published_at),
      importedAt: new Date(row.imported_at),
      areaHa: Number(row.area_ha),
      sourceAreaHa: row.source_area_ha === null ? null : Number(row.source_area_ha),
      resolutionM: row.resolution_m === null ? null : Number(row.resolution_m),
      confidenceLevel: row.confidence_level,
      method: row.method,
      sourceName: row.source_name,
      sourceAttribution: row.source_attribution,
      isCurrent: row.is_current,
      supersedesId: row.supersedes_id,
      geometry: row.geometry,
      knownAt: new Date(row.published_at ?? row.imported_at),
    })),
  );
}

/**
 * Les observations membres, les plus récentes d'abord, plafonnées à `limit`
 * (2 000 au plus, la borne de la fonction SQL). Avec `until`, ce sont les
 * observations **à cet instant** — le plafond mord sur elles, pas sur toute
 * la vie de l'événement : lire les 2 000 plus récentes puis filtrer en
 * mémoire perdait la première heure d'un événement de 2 001 observations
 * (constat 3 de l'audit du 15 septembre 2026). Les comptes d'un instant se
 * lisent dans `fetchEventState`, sans plafond.
 */
export async function fetchEventDetections(
  publicId: string,
  limit = 500,
  options: { until?: Date } = {},
): Promise<ReadResult<EventDetection[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_detections', {
    event_public_id: publicId,
    max_results: limit,
    until_at: options.until?.toISOString() ?? null,
  });

  if (error !== null) {
    console.error('[events] détections illisibles', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    acquired_at: string;
    sensor: string;
    satellite: string;
    longitude: number;
    latitude: number;
    confidence_level: 'low' | 'medium' | 'high' | 'unknown';
    frp_mw: number | null;
    day_night: string | null;
    is_known_thermal_source: boolean;
  };

  return readable(
    ((data ?? []) as Row[]).map((row) => ({
      acquiredAt: new Date(row.acquired_at),
      sensor: row.sensor,
      satellite: row.satellite,
      location: { longitude: row.longitude, latitude: row.latitude },
      confidenceLevel: row.confidence_level,
      frpMw: row.frp_mw === null ? null : Number(row.frp_mw),
      dayNight: row.day_night,
      isKnownThermalSource: row.is_known_thermal_source,
    })),
  );
}

/** L'état d'un événement à un instant, calculé en base sur toutes ses observations. */
export interface EventStateSummary {
  observationCount: number;
  /** La dernière observation réellement disponible à cet instant ; nulle si aucune. */
  effectiveAt: Date | null;
  sensors: string[];
  frpMaxMw: number | null;
}

/**
 * Compte, dernière observation effective, capteurs et FRP maximale à un
 * instant — **sans plafond** (FR-084, FR-086). C'est la source des chiffres
 * de l'état reconstitué et de la relecture ; la liste des observations, elle,
 * est plafonnée et l'annonce.
 */
export async function fetchEventState(
  publicId: string,
  until: Date,
): Promise<ReadResult<EventStateSummary>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_state', {
    event_public_id: publicId,
    until_at: until.toISOString(),
  });

  if (error !== null) {
    console.error('[events] état à un instant illisible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = {
    observation_count: number | string;
    effective_at: string | null;
    sensors: string[] | null;
    frp_max_mw: number | string | null;
  };
  const row = ((data ?? []) as Row[])[0];
  // Une fonction d'agrégat rend toujours une ligne ; l'absence en serait une
  // de PostgREST, et se lit comme « rien d'observé ».
  if (row === undefined) {
    return readable({ observationCount: 0, effectiveAt: null, sensors: [], frpMaxMw: null });
  }
  return readable({
    observationCount: Number(row.observation_count),
    effectiveAt: row.effective_at === null ? null : new Date(row.effective_at),
    sensors: row.sensors ?? [],
    frpMaxMw: row.frp_max_mw === null ? null : Number(row.frp_max_mw),
  });
}

/** Un instant d'acquisition distinct et le nombre d'observations qu'il porte. */
export interface ObservationTime {
  at: Date;
  observationCount: number;
}

/**
 * Les instants d'acquisition d'un événement, du plus ancien au plus récent —
 * les pas de la relecture (FR-080) —, sans plafond : quelques centaines au
 * plus, là où les observations se comptent en milliers.
 */
export async function fetchEventObservationTimes(
  publicId: string,
): Promise<ReadResult<ObservationTime[]>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_observation_times', {
    event_public_id: publicId,
  });

  if (error !== null) {
    console.error('[events] instants d’observation illisibles', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }

  type Row = { acquired_at: string; observation_count: number | string };
  return readable(
    ((data ?? []) as Row[]).map((row) => ({
      at: new Date(row.acquired_at),
      observationCount: Number(row.observation_count),
    })),
  );
}

/**
 * Les événements rattachés à une commune — ceux dont elle est la commune la
 * plus proche —, du plus récent au plus ancien. Cahier FR-022.
 *
 * Le rattachement existe en base depuis l'ingestion ; la page commune
 * l'affiche depuis le 15 septembre 2026. Il n'y a pas de fonction SQL par
 * commune : on lit l'emprise autour du centroïde — un quart de degré, une
 * vingtaine de kilomètres — et l'on ne garde que ce qui est rattaché à
 * **cette** commune. Un événement rattaché de plus loin — cela existe, le
 * rattachement ne connaît pas de distance — n'est pas « sur cette commune »
 * au sens où un lecteur l'entend, et n'apparaît pas ici.
 */
export async function fetchEventsNearMunicipality(
  municipality: { insee: string; centroid: { longitude: number; latitude: number } },
  options: { since?: Date; limit?: number } = {},
): Promise<ReadResult<EventSummary[]>> {
  const reach = 0.25;
  const { longitude, latitude } = municipality.centroid;
  const events = await fetchEventsInBbox(
    {
      minLon: longitude - reach,
      minLat: latitude - reach,
      maxLon: longitude + reach,
      maxLat: latitude + reach,
    },
    { limit: 500, ...(options.since === undefined ? {} : { since: options.since }) },
  );
  if (!events.readable) return unreadable();
  return readable(
    events.value
      .filter((event) => event.nearestMunicipality?.insee === municipality.insee)
      .slice(0, options.limit ?? 100),
  );
}

/**
 * L'identifiant désigne-t-il un événement **hors du périmètre** du service —
 * importé, jamais publié (ADR-027) ? Pour que la fiche dise pourquoi un lien
 * partagé ne mène à rien, plutôt qu'un 404 muet. Quand la base ne répond
 * pas, la lecture le dit : on ne prétend rien qu'on n'a pas lu, ni « hors
 * périmètre » ni « introuvable ».
 */
export async function isEventOutsideTerritory(publicId: string): Promise<ReadResult<boolean>> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('event_outside_territory', {
    event_public_id: publicId,
  });
  if (error !== null) {
    console.error('[events] périmètre illisible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return unreadable();
  }
  return readable(data === true);
}
