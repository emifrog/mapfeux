import type { Metadata, Viewport } from 'next';
import { IBM_Plex_Mono, Instrument_Sans } from 'next/font/google';
import Link from 'next/link';

import { Logo } from '@/components/logo';
import { SourceHealth } from '@/components/source-health';

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
    { media: '(prefers-color-scheme: dark)', color: '#0a1520' },
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
          <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-6 px-6">
            <Link href="/" className="text-navy flex items-center gap-2.5 dark:text-[--text]">
              <Logo className="h-[34px] w-[30px]" />
              <span>
                <span className="block text-[19px] font-bold tracking-tight">
                  Map<span className="text-age-1">Feux</span>
                </span>
                <span className="mono block text-[9.5px] uppercase tracking-[0.13em] text-[--text-3]">
                  La veille nationale des feux
                </span>
              </span>
            </Link>

            <nav aria-label="Navigation principale" className="ml-2 hidden gap-5 text-sm sm:flex">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-[--text-2] hover:text-[--text]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="ml-auto">
              <SourceHealth />
            </div>
          </div>
        </header>

        {/* Positionnement du service, présent sur toutes les pages. §1 et §22.5 */}
        <p
          className="px-6 py-2 text-center text-xs"
          style={{ background: 'var(--surface-muted)', color: 'var(--text-2)' }}
        >
          Service d’information cartographique indépendant. Ni système d’alerte, ni source de
          confirmation. Les consignes des autorités restent prioritaires.
        </p>

        <main id="contenu" className="flex-1">
          {children}
        </main>

        <footer
          className="mt-12 border-t px-6 py-10 text-sm"
          style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
        >
          <div className="mx-auto max-w-[1240px]">
            <nav aria-label="Liens de bas de page">
              <ul className="flex flex-wrap gap-x-6 gap-y-2">
                {FOOTER_LINKS.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="underline underline-offset-4">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <p className="mono mt-5 text-xs text-[--text-3]">
              Données NASA FIRMS · Météo-France · Copernicus CAMS · IGN. Attributions détaillées sur
              la page Sources.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
