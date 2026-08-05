'use client';

import { useSyncExternalStore } from 'react';

/**
 * Bascule clair / sombre — cahier §6.5.
 *
 * Trois états, pas deux. « Système » n'est pas un repli en attendant un choix :
 * c'est le réglage par défaut, et y revenir doit rester possible. Une bascule
 * binaire fige à la première pression un choix qu'on ne peut plus défaire.
 *
 * Le thème est posé sur la racine par un script en tête de document, avant le
 * premier rendu (voir `THEME_SCRIPT`). Ce composant ne fait que refléter et
 * modifier cet état : s'il le posait lui-même, la page s'afficherait d'abord
 * dans le mauvais thème le temps que React s'hydrate.
 */

export type ThemeChoice = 'system' | 'light' | 'dark';

export const THEME_STORAGE_KEY = 'mapfeux-theme';

/**
 * Script appliqué en tête de document, avant toute peinture.
 *
 * Volontairement minuscule et sans dépendance : il s'exécute de façon bloquante
 * sur le chemin critique. En cas de stockage inaccessible — navigation privée
 * verrouillée, stockage plein — l'absence d'attribut laisse simplement le
 * réglage système décider, ce qui est le comportement attendu.
 */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t)}}catch(e){}})()`;

const OPTIONS: { value: ThemeChoice; label: string; title: string }[] = [
  { value: 'light', label: 'Clair', title: 'Thème clair' },
  { value: 'system', label: 'Auto', title: 'Suivre le réglage du système' },
  { value: 'dark', label: 'Sombre', title: 'Thème sombre' },
];

/*
 * L'état vit sur la racine du document, pas dans React : c'est un script en
 * tête de page qui l'y pose. Le composant s'y abonne plutôt que d'en tenir une
 * copie — deux sources pour une même vérité finissent toujours par diverger.
 */
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function readTheme(): ThemeChoice {
  const value = document.documentElement.getAttribute('data-theme');
  return value === 'light' || value === 'dark' ? value : 'system';
}

/** Au rendu serveur, aucun choix n'est connu : le réglage système s'applique. */
function serverTheme(): ThemeChoice {
  return 'system';
}

function apply(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === 'system') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', choice);
  }

  try {
    if (choice === 'system') {
      localStorage.removeItem(THEME_STORAGE_KEY);
    } else {
      localStorage.setItem(THEME_STORAGE_KEY, choice);
    }
  } catch {
    // Le thème s'applique quand même pour cette visite ; seule la mémoire
    // manque. Échouer bruyamment pour un réglage d'affichage serait pire.
  }

  for (const listener of listeners) {
    listener();
  }
}

export function ThemeToggle() {
  const choice = useSyncExternalStore(subscribe, readTheme, serverTheme);

  return (
    <div
      role="radiogroup"
      aria-label="Thème d’affichage"
      className="mono text-micro flex items-center gap-0.5 rounded-full border p-0.5"
      style={{ borderColor: 'var(--border)' }}
    >
      {OPTIONS.map((option) => {
        const active = option.value === choice;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.title}
            onClick={() => {
              apply(option.value);
            }}
            className="rounded-full px-2.5 py-1 uppercase tracking-[0.06em]"
            style={
              active
                ? { background: 'var(--surface-muted)', color: 'var(--text)' }
                : { color: 'var(--text-3)' }
            }
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
