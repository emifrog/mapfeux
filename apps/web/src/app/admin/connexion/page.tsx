import type { Metadata } from 'next';

import { envoyerLienDeConnexion } from './actions';

/**
 * Connexion administrateur, par lien magique uniquement. Cahier §14.4.
 *
 * Pas de mot de passe : rien à voler, rien à réutiliser. Le formulaire
 * fonctionne sans JavaScript, comme le reste du site. Le proxy redirige déjà
 * les sessions actives vers /admin ; cette page ne s'affiche qu'aux visiteurs
 * sans session.
 */

export const metadata: Metadata = {
  title: 'Connexion — Administration',
  robots: { index: false, follow: false },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const sent = params['envoye'] === '1';
  const error = typeof params['erreur'] === 'string' ? params['erreur'] : null;

  return (
    <div className="shell max-w-[68ch] py-14">
      <p className="eyebrow mb-3">administration</p>

      <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        Connexion
      </h1>

      <p className="text-(--text-2) mt-4 max-w-[52ch]">
        Réservée aux administrateurs de MapFeux. Un lien de connexion à usage unique est envoyé par
        courriel — aucun mot de passe n’existe.
      </p>

      {sent && (
        <p
          role="status"
          className="border-(--border-strong) text-small mt-8 max-w-[52ch] rounded-md border px-5 py-4"
        >
          Si un compte administrateur existe pour cette adresse, un lien de connexion vient de lui
          être envoyé. Il expire rapidement et ne sert qu’une fois.
        </p>
      )}

      {error === 'lien' && (
        <p
          role="alert"
          className="border-(--border-strong) text-small mt-8 max-w-[52ch] rounded-md border px-5 py-4"
        >
          Ce lien de connexion n’est plus valable. Demandez-en un nouveau ci-dessous.
        </p>
      )}

      {error === 'email' && (
        <p role="alert" className="text-small text-(--text-2) mt-8 max-w-[52ch]">
          Adresse illisible. Vérifiez sa forme puis réessayez.
        </p>
      )}

      <form action={envoyerLienDeConnexion} className="mt-8 max-w-md">
        <label htmlFor="email" className="block text-sm font-medium">
          Adresse de courriel
        </label>
        <input
          id="email"
          name="email"
          type="email"
          required
          autoComplete="email"
          className="border-(--border-strong) mt-1 w-full rounded border px-3 py-2 text-base"
        />
        <button
          type="submit"
          className="border-(--border-strong) mt-4 rounded border px-4 py-2 font-semibold"
        >
          Recevoir un lien de connexion
        </button>
      </form>
    </div>
  );
}
