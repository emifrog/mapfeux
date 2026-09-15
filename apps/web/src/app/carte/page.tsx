import { MAP_DISCLAIMER } from '@mapfeux/domain';
import { DEFAULT_VIEW } from '@mapfeux/map-style';
import type { Metadata } from 'next';

import { CarteMapPanel } from '@/components/map/carte-map-panel';
import { FloatingCard } from '@/components/map/floating-card';
import { MunicipalitySearch } from '@/components/municipality-search';
import { fetchDepartmentAggregates } from '@/lib/data/events';
import { valueOr } from '@/lib/data/read-result';
import { toDepartmentRows } from '@/lib/map/national-scope';
import { DEFAULT_WINDOW_HOURS, windowSince } from '@/lib/map/time-windows';

/**
 * Carte nationale. Cahier §7.1, FR-001 à FR-007.
 *
 * ## Une seule carte, deux échelles — 15 septembre 2026
 *
 * La page s'ouvrait sur l'emprise pilote — le Var et les Alpes-Maritimes —
 * et annonçait quatorze événements, quand l'accueil en annonçait 646
 * « France entière » : un visiteur voyait deux services. Elle s'ouvre
 * maintenant sur la France (FR-001), et ce qu'elle lit dépend de
 * l'échelle (§21.3) : sous le zoom 7, le lavis départemental porte les
 * comptes et la colonne liste les **départements concernés** ; à partir du
 * zoom 7, les événements se chargent à l'emprise (FR-007) et la liste les
 * suit (§8.6). Aucun événement n'est servi à l'échelle nationale — la
 * France entière en un appel irait contre « ne charger que l'emprise
 * visible » (§21.4), et le plafond de surface de l'API le refuse.
 *
 * Le premier état est rendu par le serveur : les départements concernés
 * sur la fenêtre par défaut, lisibles sans JavaScript.
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
 * Sous 640 px, rien ne flotte : la carte prend une hauteur franche et tout
 * s'empile dessous, dans l'ordre de lecture.
 */

export const metadata: Metadata = {
  title: 'Carte',
  description:
    'Carte des détections thermiques satellitaires regroupées en événements, en France métropolitaine et en Corse.',
};

export const revalidate = 120;

export default async function MapPage() {
  const now = new Date();
  // La fenêtre par défaut : sept jours, la frontière que §17.4 donne à
  // l'archivage. La barre temporelle permet de la resserrer ou d'élargir
  // jusqu'à « tout ».
  const since = windowSince(DEFAULT_WINDOW_HOURS, now) ?? new Date(0);
  const aggregates = await fetchDepartmentAggregates(since);
  // Les agrégats portent nom et destination de chaque département : le
  // registre public des territoires ne dit rien des départements « à venir »
  // (FR-014), et la liste doit nommer les quatre-vingt-seize. Non lus, ils
  // ne sont pas « aucun » : le panneau le dit à la place de la liste.
  const departments = toDepartmentRows(
    valueOr(aggregates, []).map((row) => ({
      ...row,
      lastDetectedAt: row.lastDetectedAt.toISOString(),
    })),
  );

  return (
    <CarteMapPanel
      center={DEFAULT_VIEW.center}
      zoom={DEFAULT_VIEW.zoom}
      now={now}
      listEvents={[]}
      bounds={null}
      departments={departments}
      departmentsReadable={aggregates.readable}
      events={[]}
    >
      <FloatingCard>
        <nav aria-label="Fil d’Ariane" className="eyebrow flex flex-wrap items-center gap-1.5">
          <span>carte</span>
          <span aria-hidden="true" className="text-(--border-strong)">
            /
          </span>
          <span>France métropolitaine et Corse</span>
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

        {/*
          La recherche, sur la carte : c'est là qu'on cherche. Elle vivait
          sur l'accueil seulement ; les deux références regardées le
          13 septembre la posent sur la carte, et c'est le seul geste qu'on
          vient faire ici hors regarder.
        */}
        <div className="mt-4">
          <MunicipalitySearch />
        </div>
      </FloatingCard>
    </CarteMapPanel>
  );
}
