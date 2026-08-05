/**
 * Gabarit des pages de contenu.
 *
 * Colonne étroite : au-delà d'environ 70 caractères, l'œil perd la ligne
 * suivante. Ces pages sont celles que l'on lit vraiment — méthodologie,
 * limites, confidentialité — et non celles que l'on survole.
 *
 * Le surtitre en chasse fixe classe la page avant qu'on la lise : « légal »,
 * « méthode », « sources ». Six pages partagent ce gabarit et se ressemblaient
 * toutes ; savoir laquelle on a ouverte ne devrait pas demander de lire le
 * titre.
 */
export function Prose({
  eyebrow,
  title,
  lead,
  children,
}: {
  eyebrow?: string;
  title: string;
  lead?: string;
  children: React.ReactNode;
}) {
  return (
    <article className="shell max-w-[68ch] py-12">
      {eyebrow !== undefined && <p className="eyebrow mb-3">{eyebrow}</p>}

      <h1 className="text-display max-w-[19ch] text-balance font-extrabold leading-[1.06] tracking-[-0.033em]">
        {title}
      </h1>

      {lead !== undefined && <p className="text-lead text-(--text-2) mt-4">{lead}</p>}

      <div className="mt-10 flex flex-col gap-8 leading-relaxed">{children}</div>
    </article>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-title font-bold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

/**
 * Encart signalant une information manquante ou non vérifiée.
 *
 * Une page légale incomplète doit le dire en évidence. Laisser un texte
 * plausible mais faux — un nom de directeur de publication inventé, une
 * conformité non auditée — serait pire que l'absence.
 *
 * Même forme que les bandeaux d'état dégradé de la fiche événement : filet
 * porteur à gauche, fond lavé, couleur d'avertissement. Qui a vu l'un
 * reconnaît l'autre sans l'apprendre.
 */
export function ToComplete({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="text-small rounded-md border-l-[3px] px-4 py-3"
      style={{
        background: 'var(--color-degraded-wash)',
        borderColor: 'var(--color-degraded)',
        color: 'var(--color-degraded)',
      }}
    >
      {children}
    </p>
  );
}
