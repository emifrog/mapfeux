/**
 * Gabarit des pages de contenu.
 *
 * Colonne étroite : au-delà d'environ 70 caractères, l'œil perd la ligne
 * suivante. Ces pages sont celles que l'on lit vraiment — méthodologie,
 * limites, confidentialité — et non celles que l'on survole.
 */
export function Prose({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: string;
  children: React.ReactNode;
}) {
  return (
    <article className="mx-auto max-w-[68ch] px-6 py-12">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      {lead !== undefined && (
        <p className="mt-3 text-lg" style={{ color: 'var(--text-2)' }}>
          {lead}
        </p>
      )}
      <div className="mt-8 flex flex-col gap-6 leading-relaxed">{children}</div>
    </article>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
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
 */
export function ToComplete({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="rounded-xl border-l-4 p-4 text-sm"
      style={{
        background: 'var(--color-degraded-wash)',
        borderColor: 'var(--color-degraded)',
        color: 'var(--text)',
      }}
    >
      {children}
    </p>
  );
}
