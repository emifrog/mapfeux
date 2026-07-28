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
