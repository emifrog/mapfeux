import type { EventSummary } from '@/lib/data/events';

/**
 * Les événements que la carte vient de charger, rendus lisibles par la liste.
 *
 * Référence : cahier §8.6 — « liste textuelle **synchronisée** ».
 *
 * ## Le mot qui manquait
 *
 * La liste était rendue une fois par le serveur, pour l'emprise initiale, et
 * n'en bougeait plus. La carte, elle, rechargeait à chaque déplacement et à
 * chaque changement de fenêtre. Les deux comptaient donc deux choses
 * différentes, et la page le disait dans un paragraphe d'excuse : « cette
 * liste ne suit ni les déplacements de la carte ni la fenêtre que vous y
 * choisissez ». Le 12 septembre 2026, la barre annonçait 19 événements et le
 * carton juste à côté en annonçait 8. Aucun des deux ne mentait ; ensemble
 * ils étaient illisibles.
 *
 * La carte tient déjà la réponse — elle vient de la demander pour dessiner
 * ses marqueurs. Ce module la convertit ; rien n'est demandé deux fois.
 *
 * Le rendu serveur reste le premier état de la liste : sans JavaScript, elle
 * est là, complète, pour l'emprise initiale. C'est le suivi qui est un
 * supplément, pas l'existence.
 */

/** Une ligne de `GET /api/v1/events`, telle que la route la sérialise. */
export interface LoadedEventRow {
  id: string;
  freshnessStatus: string;
  verificationStatus: string;
  officialControlStatus: string | null;
  firstDetectedAt: string;
  lastDetectedAt: string;
  location: { coordinates: [number, number] };
  nearestMunicipality: { insee: string; name: string } | null;
  detectionCount: number;
  confidence: string;
}

/**
 * Convertit les lignes de l'API en résumés d'événement.
 *
 * Les dates redeviennent des `Date`, la géométrie GeoJSON redevient un
 * couple nommé : la liste et la fiche parlent la même langue depuis le
 * premier jour, et ce n'est pas à elles de s'adapter au transport.
 *
 * Les types de statut sont ceux du domaine ; l'API ne peut en servir
 * d'autres — ils sortent des mêmes colonnes contraintes — et une ligne
 * inattendue s'afficherait avec son libellé de repli plutôt que de faire
 * disparaître la liste.
 */
export function toEventSummaries(rows: readonly LoadedEventRow[]): EventSummary[] {
  return rows.map((row) => ({
    publicId: row.id,
    freshnessStatus: row.freshnessStatus as EventSummary['freshnessStatus'],
    verificationStatus: row.verificationStatus as EventSummary['verificationStatus'],
    officialControlStatus: row.officialControlStatus as EventSummary['officialControlStatus'],
    firstDetectedAt: new Date(row.firstDetectedAt),
    lastDetectedAt: new Date(row.lastDetectedAt),
    location: {
      longitude: row.location.coordinates[0],
      latitude: row.location.coordinates[1],
    },
    detectionCount: row.detectionCount,
    confidenceLevel: row.confidence as EventSummary['confidenceLevel'],
    nearestMunicipality: row.nearestMunicipality,
  }));
}
