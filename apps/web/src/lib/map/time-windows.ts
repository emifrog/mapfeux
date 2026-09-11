/**
 * Fenêtres temporelles de la carte — logique pure, testée seule.
 *
 * Référence : cahier FR-005 et §17.4.
 *
 * Le défaut vient du cahier, pas du confort : §17.4 définit `archived`
 * comme « hors fenêtre d'affichage courant », et le cycle de vie
 * (`cycle-de-vie-v1`) archive au septième jour sans observation. Sept jours
 * est donc exactement la fenêtre de ce que le domaine tient pour courant —
 * et la carte montrait jusqu'ici, sans le dire, des événements archivés
 * depuis des semaines.
 *
 * Ce module ne dépend ni de React ni du navigateur : le rendu serveur
 * l'emploie pour son premier lot, la barre pour ses boutons, et les deux
 * comptent donc la même chose.
 */

export interface TimeWindow {
  /** Heures d'historique, ou `null` pour tout ce que l'emprise porte. */
  hours: number | null;
  label: string;
}

export const TIME_WINDOWS: readonly TimeWindow[] = [
  { hours: 12, label: '12 h' },
  { hours: 24, label: '24 h' },
  { hours: 48, label: '48 h' },
  { hours: 168, label: '7 j' },
  { hours: null, label: 'Tout' },
];

/** Sept jours : la frontière de l'archivage (§17.4, cycle-de-vie-v1). */
export const DEFAULT_WINDOW_HOURS = 168;

/** L'instant de départ d'une fenêtre, ou `undefined` pour tout l'historique. */
export function windowSince(hours: number | null, now: Date = new Date()): Date | undefined {
  if (hours === null) return undefined;
  return new Date(now.getTime() - hours * 3_600_000);
}

/**
 * « dans les 12 dernières heures », « dans les 7 derniers jours ».
 *
 * La phrase accompagne toujours un compte : un filtre qui ne dit pas ce
 * qu'il retient se confond avec une absence de phénomène (§2.4).
 */
export function windowPhrase(hours: number | null): string {
  if (hours === null) return 'dans cette emprise';
  if (hours < 24) return `dans les ${hours} dernières heures`;
  const days = hours / 24;
  return days === 1 ? 'dans les dernières 24 heures' : `dans les ${days} derniers jours`;
}
