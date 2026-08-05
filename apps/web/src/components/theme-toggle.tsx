'use client';

/**
 * Bascule clair / sombre — cahier §6.5.
 *
 * Une icône, deux états. Une version antérieure en proposait trois — clair,
 * auto, sombre — pour qu'on puisse revenir au réglage du système après un choix
 * explicite. Trois libellés dans un en-tête qui doit aussi porter la marque, la
 * navigation et l'état des sources coûtaient plus de place qu'ils ne rendaient
 * de service.
 *
 * Le réglage du système reste le **défaut** : tant que rien n'est choisi, aucun
 * attribut n'est posé et la requête média décide. Ce qui disparaît est le
 * retour à ce défaut une fois qu'on l'a quitté — la contrepartie assumée d'une
 * bascule binaire.
 *
 * ## Pourquoi ce composant n'a aucun état React
 *
 * L'icône affichée est choisie par CSS, à travers la variante `dark:` — celle-là
 * même qui arbitre le thème. Les deux icônes sont dans le document ; le style
 * en montre une. Elle est donc juste avant l'hydratation, juste sans
 * JavaScript, et il n'y a aucune seconde source de vérité à tenir synchronisée
 * avec la racine du document.
 *
 * Le bouton ne lit l'état effectif qu'au moment du clic, où il est certain.
 */

export type ThemeChoice = 'light' | 'dark';

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

/**
 * Thème réellement appliqué : le choix explicite s'il existe, sinon le réglage
 * du système.
 *
 * Sans cette résolution, la première pression sur le bouton partirait d'un état
 * supposé. Sur un système en sombre et sans choix mémorisé, elle basculerait
 * vers le sombre — c'est-à-dire ne changerait rien de visible.
 */
function effectiveTheme(): ThemeChoice {
  const explicit = document.documentElement.getAttribute('data-theme');
  if (explicit === 'light' || explicit === 'dark') {
    return explicit;
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function apply(choice: ThemeChoice): void {
  document.documentElement.setAttribute('data-theme', choice);

  try {
    localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Le thème s'applique quand même pour cette visite ; seule la mémoire
    // manque. Échouer bruyamment pour un réglage d'affichage serait pire.
  }
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-4.5 dark:hidden"
    >
      <path d="M16.5 12.4A7 7 0 0 1 7.6 3.5a7 7 0 1 0 8.9 8.9Z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-4.5 hidden dark:block"
    >
      <circle cx="10" cy="10" r="3.6" />
      <path d="M10 1.8v1.8M10 16.4v1.8M3.8 3.8l1.3 1.3M14.9 14.9l1.3 1.3M1.8 10h1.8M16.4 10h1.8M3.8 16.2l1.3-1.3M14.9 5.1l1.3-1.3" />
    </svg>
  );
}

export function ThemeToggle() {
  return (
    <button
      type="button"
      onClick={() => {
        apply(effectiveTheme() === 'dark' ? 'light' : 'dark');
      }}
      className="text-(--text-2) hover:text-(--text) hover:border-(--border-strong) size-8.5 flex items-center justify-center rounded-full border"
      style={{ borderColor: 'var(--border)' }}
    >
      <MoonIcon />
      <SunIcon />
      {/*
        Le nom accessible dit l'action, pas l'état — c'est ce qu'annonce un
        lecteur d'écran avant l'activation. Les deux libellés suivent la même
        règle CSS que les icônes : `hidden` retire du rendu *et* de l'arbre
        d'accessibilité, donc un seul est annoncé.
      */}
      <span className="sr-only dark:hidden">Passer au thème sombre</span>
      <span className="sr-only hidden dark:inline">Passer au thème clair</span>
    </button>
  );
}
