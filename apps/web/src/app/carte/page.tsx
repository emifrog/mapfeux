import { MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';

import { CarteMapPanel } from '@/components/map/carte-map-panel';
import { FloatingCard } from '@/components/map/floating-card';
import { fetchEventsInBbox } from '@/lib/data/events';
import { framingBounds, framingCenter } from '@/lib/map/framing';
import { DEFAULT_WINDOW_HOURS, windowSince } from '@/lib/map/time-windows';

/**
 * Carte nationale. Cahier §7.1, FR-001 à FR-007.
 *
 * Le premier lot d'événements est chargé par le serveur : la liste textuelle
 * fonctionne sans JavaScript, et la carte affiche quelque chose sans attendre
 * un aller-retour. Les lots suivants suivent l'emprise (FR-007).
 *
 * ## Une coque d'application — refaite le 11 septembre 2026
 *
 * La page est la carte. Tout le reste flotte au-dessus : l'identité et la
 * liste à gauche, les calques à droite, la fenêtre temporelle en bas.
 *
 * La version précédente était un **document** avec une carte dedans. Mesuré
 * en 1280 × 800 : 426 px d'en-tête, de bandeau, de fil d'Ariane, de titre et
 * de paragraphe avant que la carte commence, 47 % de l'écran pour elle à
 * l'ouverture — et coupée par le pli —, 3,4 écrans de défilement en tout.
 * Une carte qu'il faut aller chercher n'est pas le sujet de sa page.
 *
 * Ce qui n'a pas bougé : rien n'est retiré. L'avertissement du §2.4 est en
 * tête du premier carton, la liste textuelle du §8.6 est toujours rendue par
 * le serveur et lisible sans JavaScript, l'attribution IGN reste permanente
 * (§9.5). Ils ont changé de place, pas de statut.
 *
 * ## Le partage gauche / droite
 *
 * À gauche ce qui **se lit** — l'identité, la liste, la légende, la
 * provenance des calques affichés. À droite ce qui **se manipule**. C'est
 * la règle qui manquait quand trois paragraphes d'explication occupaient la
 * colonne des commandes.
 *
 * La liste vit dans la coque et non ici : elle **suit la carte** (§8.6), et
 * ce que le serveur en rend n'est que son premier état — celui qui tient
 * sans JavaScript.
 *
 * Sous 640 px, rien ne flotte : la carte prend une hauteur franche et tout
 * s'empile dessous, dans l'ordre de lecture.
 */

export const metadata: Metadata = {
  title: 'Carte',
  description:
    'Carte des détections thermiques satellitaires regroupées en événements, en France métropolitaine et en Corse.',
};

export const revalidate = 120;

// Emprise de départ : les territoires pilotes. Servir la France entière
// dépasserait le plafond de surface de l'API, et n'aurait rien à montrer
// ailleurs tant que l'ingestion n'est pas nationale.
const INITIAL_BBOX = { minLon: 5.2, minLat: 42.6, maxLon: 8.0, maxLat: 44.6 };

export default async function MapPage() {
  const now = new Date();
  // Le premier lot arrive déjà dans la fenêtre par défaut : la carte et sa
  // liste montrent la même chose, et le §17.4 tient — un événement archivé
  // est « hors fenêtre d'affichage courant », pas un point de plus sur la
  // carte du jour. La barre temporelle permet d'élargir jusqu'à « tout ».
  const since = windowSince(DEFAULT_WINDOW_HOURS, now);
  const events = await fetchEventsInBbox(INITIAL_BBOX, {
    limit: 500,
    ...(since === undefined ? {} : { since }),
  });

  // Le cadrage suit ce qu'il y a à montrer : sans cela, une page intitulée
  // « anomalies thermiques observées » peut s'ouvrir sur une carte où l'on
  // n'en voit aucune, pendant que sa propre liste en annonce neuf.
  const locations = events.map((event) => event.location);
  const center = framingCenter(locations, [
    (INITIAL_BBOX.minLon + INITIAL_BBOX.maxLon) / 2,
    (INITIAL_BBOX.minLat + INITIAL_BBOX.maxLat) / 2,
  ]);
  // L'étendue prend le relais côté client, où la largeur des panneaux est
  // connue : elle seule garantit qu'aucun marqueur ne finit sous un carton.
  const bounds = framingBounds(locations);

  return (
    <CarteMapPanel
      center={center}
      zoom={8}
      now={now}
      listEvents={events}
      bounds={bounds}
      events={events.map((event) => ({
        publicId: event.publicId,
        freshnessStatus: event.freshnessStatus,
        lastDetectedAt: event.lastDetectedAt.toISOString(),
        confidence: event.confidenceLevel,
        detectionCount: event.detectionCount,
        location: event.location,
        nearestMunicipalityName: event.nearestMunicipality?.name ?? null,
      }))}
    >
      <FloatingCard>
        <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-1.5">
          <span>carte</span>
          <span aria-hidden="true" className="text-(--border-strong)">
            /
          </span>
          <span>territoires pilotes 06 et 83</span>
        </nav>

        {/*
          Le titre quitte l'échelle d'affichage — 46 px n'entrent pas dans un
          carton de 21 rem, et un titre qui déborde de son support ne se lit
          pas mieux pour être grand. Il reste le `h1` de la page.
        */}
        <h1 className="text-title mt-1.5 text-balance font-extrabold tracking-tight">
          Anomalies thermiques observées
        </h1>

        {/* §2.4 : l'avertissement précède tout ce qu'on pourrait conclure. */}
        <p className="text-small text-(--text-2) mt-2 leading-relaxed">{MAP_DISCLAIMER}</p>
      </FloatingCard>
    </CarteMapPanel>
  );
}
