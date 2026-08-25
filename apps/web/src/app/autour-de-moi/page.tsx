import type { Metadata } from 'next';
import Link from 'next/link';

import { NearMe } from '@/components/near-me';

/**
 * Page dédiée « Autour de moi » — cahier §5.3 (FR-020 à FR-024) et §22.2.
 *
 * Le bouton existait sur l'accueil ; cette page lui donne une adresse et,
 * surtout, énonce le contrat avant le geste : ce que la position sert, ce
 * qu'elle ne devient jamais. Les garanties ne sont pas des mentions en petit
 * corps après coup — elles sont le contenu de la page, lisible avant de
 * cliquer, et sans JavaScript la page reste entière : elle explique, et
 * renvoie vers la recherche par nom qui n'exige rien.
 */

export const metadata: Metadata = {
  title: 'Autour de moi',
  description:
    'Ouvrir la commune où vous vous trouvez, sans que votre position soit stockée : arrondie à environ cent mètres, traitée ponctuellement, jamais conservée.',
};

const GUARANTEES = [
  {
    title: 'La permission est demandée au clic, jamais au chargement.',
    detail:
      'Rien ne se passe avant que vous n’appuyiez sur le bouton, et le refus est respecté sans insistance (FR-020).',
  },
  {
    title: 'La position est arrondie avant de quitter votre appareil.',
    detail:
      'À la troisième décimale — une centaine de mètres. Assez pour résoudre une commune, pas pour désigner une adresse (§22.2).',
  },
  {
    title: 'Elle est traitée ponctuellement, puis oubliée.',
    detail:
      'Elle sert à trouver votre commune, voyage en corps de requête — jamais dans une adresse web, donc jamais dans les journaux des CDN — et n’est ni stockée ni journalisée (FR-021, FR-022).',
  },
  {
    title: 'Refuser ne dégrade rien.',
    detail:
      'La recherche par nom reste entière, et aucune mesure d’audience ne reçoit de coordonnées (FR-023, FR-024).',
  },
] as const;

export default function NearMePage() {
  return (
    <div className="shell max-w-[75ch] py-14">
      <p className="eyebrow">position</p>
      <h1 className="text-display mt-3 max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Autour de moi
      </h1>
      <p className="text-lead text-(--text-2) mt-4 max-w-[58ch]">
        Ouvre la page de la commune où vous vous trouvez. Voici exactement ce que votre position
        sert — et ce qu’elle ne devient jamais.
      </p>

      <ul className="mt-8 max-w-[60ch] space-y-4">
        {GUARANTEES.map((guarantee) => (
          <li key={guarantee.title}>
            <p className="font-semibold">{guarantee.title}</p>
            <p className="text-small text-(--text-2) mt-1">{guarantee.detail}</p>
          </li>
        ))}
      </ul>

      <p className="mt-10 text-lg">
        <NearMe />
      </p>

      {/* Sans JavaScript, le bouton ne peut pas agir : le chemin de repli est
          le même que celui d'un refus — la recherche par nom, intacte. */}
      <noscript>
        <p className="text-small text-(--text-2) mt-4 max-w-[52ch]">
          Ce bouton nécessite JavaScript. Sans lui, la{' '}
          <Link href="/" className="underline underline-offset-4">
            recherche par nom de commune
          </Link>{' '}
          rend le même service, sans position.
        </p>
      </noscript>

      <p className="text-small text-(--text-2) mt-10">
        Le détail de ces engagements est dans la{' '}
        <Link href="/confidentialite" className="underline underline-offset-4">
          politique de confidentialité
        </Link>
        .
      </p>
    </div>
  );
}
