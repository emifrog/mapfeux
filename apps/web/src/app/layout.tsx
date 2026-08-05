import type { Metadata, Viewport } from 'next';
import { IBM_Plex_Mono, Instrument_Sans } from 'next/font/google';
import Link from 'next/link';

import { Logo } from '@/components/logo';
import { SourceHealth } from '@/components/source-health';
import { THEME_SCRIPT, ThemeToggle } from '@/components/theme-toggle';

import './globals.css';

/**
 * Polices auto-hébergées par Next au moment de la construction.
 *
 * Aucune requête vers Google Fonts à l'exécution : c'est une dépendance
 * externe de moins sur le chemin critique, et une CSP stricte le permettra
 * sans exception (§22.4).
 */
const sans = Instrument_Sans({
  subsets: ['latin'],
  variable: '--font-instrument-sans',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'MapFeux — la veille nationale des feux',
    template: '%s — MapFeux',
  },
  description:
    'Carte publique des détections thermiques satellitaires, des événements probables et des informations officielles attribuées. Service d’information, non officiel.',
  applicationName: 'MapFeux',
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f6f8fa' },
    { media: '(prefers-color-scheme: dark)', color: '#080d15' },
  ],
  width: 'device-width',
  initialScale: 1,
};

const NAV = [
  { href: '/carte', label: 'Carte' },
  { href: '/statut', label: 'Statut' },
  { href: '/methodologie', label: 'Méthode' },
] as const;

const FOOTER_LINKS = [
  { href: '/sources', label: 'Sources et licences' },
  { href: '/methodologie', label: 'Méthodologie' },
  { href: '/statut', label: 'État des données' },
  { href: '/a-propos', label: 'À propos' },
  { href: '/mentions-legales', label: 'Mentions légales' },
  { href: '/confidentialite', label: 'Confidentialité' },
  { href: '/accessibilite', label: 'Accessibilité' },
] as const;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <head>
        {/*
          Le thème choisi est posé sur la racine avant la première peinture. Le
          faire dans un effet afficherait d'abord le mauvais thème, le temps que
          React s'hydrate — un clignotement blanc en pleine nuit sur une carte de
          feux.
        */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:px-4 focus:py-2"
          style={{ background: 'var(--surface)' }}
        >
          Aller au contenu principal
        </a>

        <header
          className="sticky top-0 z-20 border-b"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <div className="shell h-16.5 flex items-center gap-7">
            <Link href="/" className="text-navy dark:text-(--text) flex items-center gap-2.5">
              <Logo className="w-8.75 h-10" />
              <span>
                <span className="text-(length:--text-title) block font-extrabold tracking-tight">
                  Map<span className="text-age-1">Feux</span>
                </span>
                <span className="mono text-(length:--text-micro) text-(--text-3) mt-0.5 block uppercase tracking-[0.14em]">
                  La veille nationale des feux
                </span>
              </span>
            </Link>

            <nav
              aria-label="Navigation principale"
              className="text-(length:--text-body) ml-2 hidden gap-6 sm:flex"
            >
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-(--text-2) hover:border-(--border-strong) hover:text-(--text) border-b-2 border-transparent py-1"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="ml-auto flex items-center gap-3">
              <div className="hidden sm:block">
                <ThemeToggle />
              </div>
              <SourceHealth />
            </div>
          </div>
        </header>

        {/*
          Positionnement du service, présent sur toutes les pages. §1 et §22.5
          Aligné à gauche dans la colonne de lecture, clause décisive en gras :
          ce qui ressemble à du contenu se lit, ce qui ressemble à un bandeau de
          consentement se saute.
        */}
        <div className="stance">
          <div className="shell flex items-baseline gap-3 py-3">
            <span className="stance__rule" aria-hidden="true" />
            <p className="text-(length:--text-small) text-(--text-2) max-w-[88ch]">
              Service d’information cartographique indépendant.{' '}
              <strong className="text-(--text) font-semibold">
                Ni système d’alerte, ni source de confirmation.
              </strong>{' '}
              Les consignes des autorités restent prioritaires.
            </p>
          </div>
        </div>

        <main id="contenu" className="flex-1">
          {children}
        </main>

        <footer
          className="text-(length:--text-small) mt-16 border-t py-10"
          style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
        >
          <div className="shell">
            <nav aria-label="Liens de bas de page">
              <ul className="flex flex-wrap gap-x-6 gap-y-2">
                {FOOTER_LINKS.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="hover:text-(--text) underline underline-offset-4"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            {/* L'attribution IGN est obligatoire et permanente (§9.5). */}
            <p className="mono text-(length:--text-label) text-(--text-3) mt-5">
              Données NASA FIRMS · Météo-France · Copernicus CAMS · IGN Géoplateforme. Attributions
              détaillées sur la page Sources.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
