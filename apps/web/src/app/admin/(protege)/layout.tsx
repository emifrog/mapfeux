import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ADMIN_ROLE_LABELS, fetchAdminProfile } from '@/lib/data/admin';
import { createPublicServerClient } from '@/lib/supabase/server';

import { seDeconnecter } from './actions';

/**
 * Garde de l'administration. Cahier §14.1, §14.2 et §7.2.
 *
 * Le proxy a déjà exigé une session ; ce layout vérifie ce que le proxy ne
 * regarde pas — l'existence d'un profil administrateur **actif** et son rôle,
 * lus en base par `api.admin_profile()`. Une session sans profil actif voit
 * une impasse explicite, pas une redirection : boucler vers la connexion
 * laisserait croire que réessayer changera quelque chose.
 *
 * Ce rôle guide l'interface ; il ne la protège pas. Chaque écriture future
 * revérifiera l'habilitation en base (`admin.has_role`), car un layout se
 * contourne — pas une politique RLS.
 */

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createPublicServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Défense en profondeur : le proxy fait déjà cette vérification, mais un
  // layout ne doit pas dépendre de la configuration d'un matcher.
  if (user === null) {
    redirect('/admin/connexion');
  }

  const profile = await fetchAdminProfile(supabase);

  if (profile === null || profile.status !== 'active') {
    return (
      <div className="shell max-w-[68ch] py-14">
        <p className="eyebrow mb-3">administration</p>
        <h1 className="text-display max-w-[17ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
          Compte sans habilitation
        </h1>
        <p className="text-(--text-2) mt-4 max-w-[52ch]">
          Cette session est authentifiée, mais aucun profil administrateur actif ne lui est
          rattaché. Les habilitations sont attribuées individuellement — rien ne s’obtient depuis
          cette page.
        </p>
        <form action={seDeconnecter} className="mt-8">
          <button
            type="submit"
            className="border-(--border-strong) rounded border px-4 py-2 font-semibold"
          >
            Se déconnecter
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="shell py-10">
      <header className="border-(--border) flex flex-wrap items-baseline gap-x-6 gap-y-2 border-b pb-4">
        <p className="eyebrow">administration</p>
        <p className="text-small text-(--text-2)">
          {profile.displayName} · <span className="mono">{user.email}</span> ·{' '}
          {ADMIN_ROLE_LABELS[profile.role] ?? profile.role}
        </p>
        <div className="ml-auto flex items-baseline gap-4">
          <Link href="/" className="text-small underline underline-offset-4">
            Site public
          </Link>
          <form action={seDeconnecter}>
            <button type="submit" className="text-small underline underline-offset-4">
              Se déconnecter
            </button>
          </form>
        </div>
      </header>
      {children}
    </div>
  );
}
