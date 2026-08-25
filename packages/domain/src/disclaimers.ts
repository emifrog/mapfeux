/**
 * Formulations publiques obligatoires.
 *
 * Référence : cahier §22.5. Ces textes sont validés métier ; ils ne doivent pas
 * être reformulés dans les composants d'interface. Toute évolution passe par une
 * revue et met à jour ce fichier, qui fait foi.
 */

export const MAP_DISCLAIMER =
  'Les points affichés sont des détections thermiques satellitaires. Ils peuvent correspondre à un incendie, mais aussi à une autre source de chaleur. Un feu récent peut ne pas encore être détecté. Consultez les informations officielles des autorités.';

export const SMOKE_DISCLAIMER =
  'Projection indicative calculée à partir des données de vent disponibles. Elle ne tient pas complètement compte du relief, des brises locales, de la convection et de la hauteur réelle des fumées.';

export const EVENT_DISCLAIMER =
  'Événement déduit de détections satellitaires, non équivalent à une confirmation officielle.';

export const DETECTION_PIXEL_NOTICE =
  "Un point correspond au centre approximatif d'un pixel satellite et non nécessairement au foyer exact.";

export const MODELLED_VALUE_NOTICE =
  "Donnée modélisée issue d'une grille de prévision, et non d'une mesure locale.";

// FR-093 : un périmètre satellitaire ou estimé n'est jamais présenté comme un
// contour opérationnel. La phrase accompagne toute version de ces natures.
export const PERIMETER_DISCLAIMER =
  "Périmètre indicatif établi à partir de produits satellitaires ou d'estimations. Ce n'est pas un contour opérationnel.";

export const OFFLINE_NOTICE =
  'Mode hors connexion : les informations affichées proviennent du cache et ne sont pas à jour.';
