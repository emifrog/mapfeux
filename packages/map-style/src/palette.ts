/**
 * Système visuel cartographique.
 * Référence : cahier §8.2.
 *
 * Le rouge et l'orange sont réservés aux phénomènes thermiques : aucun autre
 * élément d'interface ne doit les employer, sous peine de suggérer une alerte.
 * Le gris marque l'ancienneté ; le bleu et le violet la météo et l'air.
 *
 * Chaque couleur porte un second signal — forme, contour ou libellé — afin que
 * la légende ne repose jamais uniquement sur la couleur. §6.5
 */

export const PALETTE = {
  /** Détections et événements thermiques, du plus récent au plus ancien. */
  thermal: {
    new: '#dc2626',
    recent: '#ea580c',
    notRecent: '#a16207',
    archived: '#78716c',
  },
  /** Données anciennes ou non revues. */
  neutral: {
    strong: '#57534e',
    muted: '#a8a29e',
    faint: '#e7e5e4',
  },
  /** Météo, vent et qualité de l'air. */
  atmosphere: {
    wind: '#2563eb',
    smoke: '#7c3aed',
    airQuality: '#4f46e5',
    precipitation: '#0891b2',
  },
  /** Information officielle : jamais rouge, pour ne pas imiter une alerte. */
  official: '#0f766e',
  boundary: '#44403c',
} as const;

/** Couleur d'un événement selon sa fraîcheur technique. */
export const FRESHNESS_COLORS: Record<string, string> = {
  new: PALETTE.thermal.new,
  recent: PALETTE.thermal.recent,
  not_recent: PALETTE.thermal.notRecent,
  archived: PALETTE.thermal.archived,
  hidden: PALETTE.neutral.faint,
};

/**
 * Symbole distinct pour chaque nature d'objet, indépendamment de la couleur.
 * Une détection brute et un événement regroupé ne partagent jamais la même
 * forme. §8.2
 */
export const SYMBOLS = {
  rawDetection: 'circle',
  groupedEvent: 'triangle',
  officialMessage: 'square',
} as const;

/** Motif de remplissage du panache : contour pointillé, jamais plein opaque. */
export const SMOKE_FILL_OPACITY = 0.18;
export const SMOKE_OUTLINE_DASH: readonly [number, number] = [2, 2];
