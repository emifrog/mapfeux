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

/**
 * Accès aux événements.
 *
 * Référence : cahier §5.6 et §5.7.
 *
 * La fiche doit être rendue côté serveur et rester lisible sans JavaScript
 * (FR-051). Tout ce qu'elle affiche est donc chargé ici, en trois requêtes au
 * plus, avant le premier octet envoyé au navigateur.
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
 * Retourne `null` si l'événement n'existe pas ou a été masqué.
 *
 * Le masquage est traité en base : un événement retiré du public l'est aussi
 * par son URL directe (§17.7).
 */
export async function fetchEvent(publicId: string): Promise<FireEvent | null> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event', { event_public_id: publicId });

  if (error !== null) {
    console.error('[events] lecture impossible', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return null;
  }

  const rows = (data ?? []) as EventRow[];
  const first = rows[0];
  return first === undefined ? null : toEvent(first);
}

/**
 * Résout un identifiant fusionné vers l'événement canonique.
 * Retourne `null` si l'identifiant n'est connu ni comme événement, ni comme
 * alias — permet à l'appelant de distinguer une redirection d'un 404 (§13.10).
 */
export async function resolveEventAlias(candidate: string): Promise<string | null> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('resolve_event_alias', {
    candidate_public_id: candidate,
  });

  if (error !== null) {
    console.error('[events] résolution d’alias impossible', {
      code: error.code,
      message: error.message,
    });
    return null;
  }

  return (data as string | null) ?? null;
}

export async function fetchEventTimeline(publicId: string): Promise<TimelineEntry[]> {
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
    return [];
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

  return ((data ?? []) as Row[]).map((row) => ({
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
  }));
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
  readonly timeline: TimelineEntry[];
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

export async function fetchEventView(publicId: string): Promise<EventView | null> {
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
      return {
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
        timeline: p.timeline.map((entry) => ({
          id: entry.id,
          entryType: entry.entryType,
          provenance: entry.provenance,
          occurredAt: new Date(entry.occurredAt),
          recordedAt: new Date(entry.recordedAt),
          title: entry.title,
          summary: entry.summary,
          source: entry.source,
        })),
      };
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
  // seulement plus coûteuse.
  const event = await fetchEvent(publicId);
  if (event === null) return null;

  return {
    origin: 'live',
    generatedAt: null,
    event,
    timeline: await fetchEventTimeline(event.publicId),
  };
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
): Promise<{ events: EventSummary[]; nextCursor: string | null }> {
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
    console.error('[events] catalogue indisponible', {
      code: error.code,
      message: error.message,
    });
    return { events: [], nextCursor: null };
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

  return { events, nextCursor };
}

export interface DepartmentAggregateRow {
  departmentCode: string;
  departmentSlug: string;
  departmentStatus: string;
  events: number;
  substantiated: number;
  lastDetectedAt: Date;
}

/**
 * Comptes d'événements visibles par département. FR-003 et §21.2.
 *
 * L'agrégat est calculé en base depuis la même vue que la carte : ce que la
 * vue masque, l'agrégat l'ignore par construction. Un département absent du
 * résultat n'a simplement aucun événement sur la période.
 */
export async function fetchDepartmentAggregates(since: Date): Promise<DepartmentAggregateRow[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('department_event_aggregates', {
    since: since.toISOString(),
  });

  if (error !== null) {
    console.error('[events] agrégats départementaux indisponibles', {
      code: error.code,
      message: error.message,
    });
    return [];
  }

  type Row = {
    department_code: string;
    department_slug: string;
    department_status: string;
    events: number;
    substantiated: number;
    last_detected_at: string;
  };

  return ((data ?? []) as Row[]).map((row) => ({
    departmentCode: row.department_code,
    departmentSlug: row.department_slug,
    departmentStatus: row.department_status,
    events: row.events,
    substantiated: row.substantiated,
    lastDetectedAt: new Date(row.last_detected_at),
  }));
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
): Promise<EventSummary[]> {
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
    return [];
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

  return ((data ?? []) as Row[]).map((row) => ({
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
}

export async function fetchEventDetections(
  publicId: string,
  limit = 500,
): Promise<EventDetection[]> {
  const supabase = createPublicReadClient();
  const { data, error } = await supabase.rpc('fire_event_detections', {
    event_public_id: publicId,
    max_results: limit,
  });

  if (error !== null) {
    console.error('[events] détections illisibles', {
      publicId,
      code: error.code,
      message: error.message,
    });
    return [];
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

  return ((data ?? []) as Row[]).map((row) => ({
    acquiredAt: new Date(row.acquired_at),
    sensor: row.sensor,
    satellite: row.satellite,
    location: { longitude: row.longitude, latitude: row.latitude },
    confidenceLevel: row.confidence_level,
    frpMw: row.frp_mw === null ? null : Number(row.frp_mw),
    dayNight: row.day_night,
    isKnownThermalSource: row.is_known_thermal_source,
  }));
}
