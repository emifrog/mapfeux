import type { Metadata, Viewport } from 'next';
import Link from 'next/link';

import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'MapFeux — détections thermiques et fumées',
    template: '%s — MapFeux',
  },
  description:
    'Carte publique des détections thermiques satellitaires, des événements probables et des panaches de fumée indicatifs en France. Service d’information, non officiel.',
  applicationName: 'MapFeux',
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: '#1c1917',
  width: 'device-width',
  initialScale: 1,
};

/**
 * Bandeau de positionnement, présent sur toutes les pages.
 * Cahier §1 et §22.5 : le caractère non officiel du service doit être
 * compréhensible en moins de cinq secondes, sans ouvrir de page secondaire.
 */
function ServiceNotice() {
  return (
    <p className="bg-stone-800 px-4 py-2 text-center text-xs text-stone-100">
      Service d’information cartographique indépendant. Ni système d’alerte, ni source de
      confirmation. Les consignes des autorités restent prioritaires.
    </p>
  );
}

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
    <html lang="fr" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:px-4 focus:py-2"
        >
          Aller au contenu principal
        </a>

        <ServiceNotice />

        <header className="border-b border-stone-200 px-4 py-3">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            MapFeux
          </Link>
        </header>

        <main id="contenu" className="flex-1">
          {children}
        </main>

        <footer className="border-t border-stone-200 px-4 py-6 text-sm">
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
          <p className="mt-4 text-xs text-stone-500">
            Données NASA FIRMS, Météo-France, Copernicus CAMS et IGN. Attributions détaillées sur la
            page Sources.
          </p>
        </footer>
      </body>
    </html>
  );
}
