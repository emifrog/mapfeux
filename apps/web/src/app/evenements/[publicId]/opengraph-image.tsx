import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { EVENT_DISCLAIMER } from '@mapfeux/domain';
import { CONFIDENCE_LEVEL_LABELS, VERIFICATION_STATUS_LABELS } from '@mapfeux/ui';
import { ImageResponse } from 'next/og';

import { fetchEventView } from '@/lib/data/events';

/**
 * Carte de partage Open Graph — cahier v2.1, FR-067.
 *
 * Générée depuis le **snapshot** (même chemin d'accès que la fiche, §21.5) et
 * porteuse des deux mentions que le partage social fait habituellement
 * disparaître : l'avertissement — un événement déduit n'est pas une
 * confirmation — et l'horodatage de la donnée. Une image partagée vit sans son
 * contexte ; elle doit donc l'embarquer.
 *
 * Deux horodatages figurent sur la carte : celui de la dernière observation et
 * celui de la construction de l'état figé. L'heure de service, elle, n'y a pas
 * sa place : l'image est mise en cache, l'y inscrire ferait passer une carte
 * ancienne pour fraîche — l'inverse exact de ce que demande le §21.5.
 */

export const revalidate = 120;

export const alt =
  'Anomalies thermiques observées par satellite — synthèse de partage MapFeux, avec horodatage et avertissement';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

/*
 * Le moteur de rendu (Satori) ne lit ni les variables CSS ni les feuilles de
 * style : les jetons de `globals.css` sont recopiés ici en clair, thème clair
 * uniquement — une image n'a pas de préférence système à suivre. Toute retouche
 * des jetons doit être répercutée à la main.
 */
const TOKENS = {
  bg: '#f6f8fa',
  surface: '#ffffff',
  surfaceMuted: '#eef2f5',
  border: '#d9e0e6',
  text: '#021526',
  text2: '#4d5a6b',
  text3: '#798591',
  degraded: '#8b5e12',
  degradedWash: '#fbf2e0',
} as const;

/**
 * L'orange appartient à l'observation thermique et à elle seule : la pastille
 * reprend l'échelle d'âge de la carte, du rouge vif au gris d'archive.
 */
const THERMAL_BY_FRESHNESS: Record<string, string> = {
  new: '#ce2516',
  recent: '#ee5718',
  not_recent: '#f0a24e',
  archived: '#97a0aa',
  hidden: '#97a0aa',
};

/**
 * Polices du site en WOFF v1, seul format des dérivés fontsource que le moteur
 * accepte (pas de woff2), recopiées dans `assets/og-fonts/` avec leurs
 * licences. Chaque lecture est un chemin **littéral** : c'est ce qui permet au
 * traçage de fichiers du déploiement de les embarquer. La première version
 * composait les chemins depuis un tableau et lisait node_modules — intraçable
 * statiquement : parfaite en local, 500 en production.
 */
const FONTS_DIR = join(process.cwd(), 'assets', 'og-fonts');

async function loadFonts() {
  const [sans400, sans600, sans700, mono400, mono600] = await Promise.all([
    readFile(join(FONTS_DIR, 'instrument-sans-latin-400-normal.woff')),
    readFile(join(FONTS_DIR, 'instrument-sans-latin-600-normal.woff')),
    readFile(join(FONTS_DIR, 'instrument-sans-latin-700-normal.woff')),
    readFile(join(FONTS_DIR, 'ibm-plex-mono-latin-400-normal.woff')),
    readFile(join(FONTS_DIR, 'ibm-plex-mono-latin-600-normal.woff')),
  ]);
  return [
    { name: 'Instrument Sans', data: sans400, weight: 400 as const, style: 'normal' as const },
    { name: 'Instrument Sans', data: sans600, weight: 600 as const, style: 'normal' as const },
    { name: 'Instrument Sans', data: sans700, weight: 700 as const, style: 'normal' as const },
    { name: 'IBM Plex Mono', data: mono400, weight: 400 as const, style: 'normal' as const },
    { name: 'IBM Plex Mono', data: mono600, weight: 600 as const, style: 'normal' as const },
  ];
}

function formatInstant(value: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone,
  }).format(value);
}

interface PageParams {
  params: Promise<{ publicId: string }>;
}

export default async function OpenGraphImage({ params }: PageParams) {
  const { publicId } = await params;
  const view = await fetchEventView(publicId);

  // Pas de redirection d'alias ici : c'est la page qui redirige, et le
  // moissonneur du réseau social redemandera l'image sous l'URL canonique.
  if (view === null) {
    return new Response('Événement introuvable', { status: 404 });
  }

  const { event } = view;
  const thermal = THERMAL_BY_FRESHNESS[event.freshnessStatus] ?? '#97a0aa';
  const place = event.nearestMunicipality?.name ?? null;
  const title =
    place === null ? 'Anomalies thermiques observées' : `Anomalies thermiques près de ${place}`;
  const isFixture = event.publicId.startsWith('DEMO-');

  const figures = [
    {
      value: String(event.detectionCount),
      label: event.detectionCount > 1 ? 'observations' : 'observation',
    },
    { value: String(event.sensorCount), label: event.sensorCount > 1 ? 'capteurs' : 'capteur' },
    {
      value: event.frp.max === null ? '—' : `${event.frp.max} MW`,
      label: 'puissance radiative max.',
    },
    { value: CONFIDENCE_LEVEL_LABELS[event.confidenceLevel], label: 'fiabilité estimée' },
  ];

  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: TOKENS.bg,
        color: TOKENS.text,
        fontFamily: 'Instrument Sans',
        padding: '52px 64px 48px',
      }}
    >
      {/* En-tête : marque à gauche, identifiant public en chasse fixe à droite. */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 30, fontWeight: 700, letterSpacing: -0.5 }}>MapFeux</span>
          <span
            style={{
              fontFamily: 'IBM Plex Mono',
              fontSize: 19,
              color: TOKENS.text3,
              textTransform: 'uppercase',
              letterSpacing: 2,
            }}
          >
            observation satellitaire
          </span>
        </div>
        <span style={{ fontFamily: 'IBM Plex Mono', fontSize: 26, color: TOKENS.text2 }}>
          {event.publicId}
        </span>
      </div>

      {/* Corps : niveau de vérification, titre, grandeurs mesurées. */}
      <div
        style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, justifyContent: 'center' }}
      >
        <div style={{ display: 'flex' }}>
          <span
            style={{
              display: 'flex',
              background: TOKENS.surfaceMuted,
              border: `1px solid ${TOKENS.border}`,
              borderRadius: 999,
              padding: '8px 22px',
              fontSize: 23,
              fontWeight: 600,
            }}
          >
            {VERIFICATION_STATUS_LABELS[event.verificationStatus]}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            fontSize: title.length > 42 ? 52 : 60,
            fontWeight: 700,
            letterSpacing: -1.6,
            lineHeight: 1.08,
            marginTop: 22,
            maxWidth: 1020,
          }}
        >
          {title}
        </div>

        {/* Ce qui est mesuré est en chasse fixe, comme sur la fiche. */}
        <div style={{ display: 'flex', gap: 56, marginTop: 40 }}>
          {figures.map((figure) => (
            <div key={figure.label} style={{ display: 'flex', flexDirection: 'column' }}>
              <span
                style={{
                  fontFamily: 'IBM Plex Mono',
                  fontSize: 42,
                  fontWeight: 600,
                  letterSpacing: -1,
                }}
              >
                {figure.value}
              </span>
              <span style={{ fontSize: 21, color: TOKENS.text2, marginTop: 4 }}>
                {figure.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Pied : horodatages, puis avertissement — les deux mentions de FR-067. */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span
            style={{
              display: 'flex',
              width: 16,
              height: 16,
              borderRadius: 999,
              background: thermal,
            }}
          />
          <span style={{ fontFamily: 'IBM Plex Mono', fontSize: 21 }}>
            Dernière observation : {formatInstant(event.lastDetectedAt, event.timeZone)}
          </span>
          <span style={{ fontFamily: 'IBM Plex Mono', fontSize: 21, color: TOKENS.text3 }}>
            {view.generatedAt === null
              ? '· état lu en base'
              : `· état figé du ${formatInstant(view.generatedAt, event.timeZone)}`}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            marginTop: 18,
            borderLeft: `5px solid ${TOKENS.degraded}`,
            background: TOKENS.degradedWash,
            color: TOKENS.degraded,
            borderRadius: 8,
            padding: '14px 20px',
            fontSize: 21,
            fontWeight: 600,
            lineHeight: 1.35,
          }}
        >
          {isFixture
            ? 'Jeu de démonstration : ces détections sont inventées et ne correspondent à aucune observation réelle.'
            : EVENT_DISCLAIMER}
        </div>
      </div>
    </div>,
    { ...size, fonts: await loadFonts() },
  );
}
