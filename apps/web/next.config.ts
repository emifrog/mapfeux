import type { NextConfig } from 'next';

/**
 * En-têtes de sécurité appliqués à toutes les réponses.
 *
 * Référence : cahier §22.4.
 *
 * La CSP complète n'est pas encore posée : Next injecte des scripts inline dont
 * la mise en nonce passe par `proxy.ts`. La poser à moitié, avec
 * `unsafe-inline`, donnerait une fausse impression de protection. Elle est
 * traitée dans EPIC-10 avec le test de pénétration associé.
 */
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload',
  },
  // La géolocalisation reste autorisée pour « Autour de moi », uniquement sur
  // notre propre origine et après consentement explicite. FR-023, §22.2
  {
    key: 'Permissions-Policy',
    value: 'geolocation=(self), camera=(), microphone=(), payment=(), usb=()',
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Les packages du monorepo sont publiés en TypeScript source.
  transpilePackages: ['@mapfeux/ui', '@mapfeux/domain', '@mapfeux/contracts', '@mapfeux/map-style'],

  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  },

  /**
   * Anciens chemins, renommés le 6 août 2026 pour s'aligner sur le cahier
   * v2.1 (§7.1 et §15.2) avant que la moindre URL ne devienne permanente.
   * Le site étant déjà déployé, un lien copié hier doit continuer de porter.
   * 308 : le renommage est définitif, les moteurs peuvent oublier l'ancien.
   */
  async redirects() {
    return [
      { source: '/commune/:insee', destination: '/communes/:insee', permanent: true },
      { source: '/territoire/:slug', destination: '/territoires/:slug', permanent: true },
      {
        source: '/api/v1/fires/:publicId/detections',
        destination: '/api/v1/events/:publicId/observations',
        permanent: true,
      },
      { source: '/api/v1/fires/:path*', destination: '/api/v1/events/:path*', permanent: true },
    ];
  },
};

export default nextConfig;
