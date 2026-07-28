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
  /**
   * Âge de l'observation thermique, du plus récent au plus ancien.
   *
   * La carte colore par **âge** et non par statut de fraîcheur. Les deux
   * répondent à des questions différentes : le statut dit ce que l'on sait de
   * l'événement, l'âge dit à quel point l'image est vieille. Sur une carte,
   * c'est la seconde qui se lit d'un coup d'œil.
   */
  thermal: {
    /** Moins de 3 heures. */
    new: '#ce2516',
    /** De 3 à 12 heures. */
    recent: '#ee5718',
    /** De 12 à 24 heures. */
    notRecent: '#f0a24e',
    /** Au-delà de 24 heures. */
    archived: '#97a0aa',
  },
  neutral: {
    strong: '#2a3646',
    muted: '#97a0aa',
    faint: '#eef2f5',
  },
  /** Météo, vent et qualité de l'air. */
  atmosphere: {
    wind: '#17639e',
    smoke: '#6941c6',
    airQuality: '#6941c6',
    precipitation: '#17639e',
  },
  /** Information officielle : bleu, jamais rouge, pour ne pas imiter une alerte. */
  official: '#17639e',
  /** Produit d'un calcul, distinct de l'observé et de l'officiel. */
  inference: '#6941c6',
  boundary: '#c4cbd3',
} as const;

/** Seuils d'âge de la légende cartographique, en heures. */
export const AGE_BUCKETS_HOURS = { new: 3, recent: 12, notRecent: 24 } as const;

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

/**
 * Expression MapLibre coloriant un événement selon sa fraîcheur technique.
 *
 * Écrite ici plutôt que dans le composant : la correspondance entre un statut
 * et une couleur est une règle du système visuel (§8.2), pas un détail de
 * rendu. Elle doit rester identique entre la carte, la légende et tout futur
 * export.
 */
export const FRESHNESS_COLOR_EXPRESSION = [
  'step',
  ['get', 'ageHours'],
  PALETTE.thermal.new,
  AGE_BUCKETS_HOURS.new,
  PALETTE.thermal.recent,
  AGE_BUCKETS_HOURS.recent,
  PALETTE.thermal.notRecent,
  AGE_BUCKETS_HOURS.notRecent,
  PALETTE.thermal.archived,
] as const;

/** Bucket d'âge d'une observation, pour la légende et la liste textuelle. */
export function ageBucket(hours: number): 'new' | 'recent' | 'notRecent' | 'archived' {
  if (hours < AGE_BUCKETS_HOURS.new) return 'new';
  if (hours < AGE_BUCKETS_HOURS.recent) return 'recent';
  if (hours < AGE_BUCKETS_HOURS.notRecent) return 'notRecent';
  return 'archived';
}

/**
 * Rayon d'un marqueur selon le nombre de détections.
 *
 * La taille suit le nombre d'observations, **pas** la surface ni la gravité du
 * phénomène, que nous ne connaissons pas. La légende doit le dire, faute de
 * quoi un gros cercle se lira comme un gros feu (FR-049).
 */
export const DETECTION_COUNT_RADIUS_EXPRESSION = [
  'interpolate',
  ['linear'],
  ['get', 'detectionCount'],
  1,
  5,
  10,
  9,
  50,
  14,
  500,
  20,
] as const;
