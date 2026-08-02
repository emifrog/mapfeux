'use client';

import { useState } from 'react';

/**
 * Copie de l'URL permanente.
 *
 * Référence : cahier FR-054 et le critère de sortie du jalon J1 — la fiche doit
 * rester complète sans JavaScript.
 *
 * Ce bouton est une commodité, pas le moyen de partager : l'URL canonique est
 * rendue côté serveur juste à côté, sous forme de lien cliquable et
 * sélectionnable. Sans JavaScript, on perd le bouton, pas la fonction.
 */
export function ShareLink({ url }: { url: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setState('copied');
    } catch {
      // Presse-papiers refusé — contexte non sécurisé ou permission absente.
      // L'utilisateur peut toujours sélectionner le lien affiché.
      setState('failed');
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void copy()}
        className="rounded border border-[--border-strong] px-3 py-1 text-sm"
      >
        Copier le lien
      </button>
      <span role="status" aria-live="polite" className="text-sm text-[--text-2]">
        {state === 'copied' && 'Lien copié'}
        {state === 'failed' && 'Copie impossible, sélectionnez le lien'}
      </span>
    </span>
  );
}
