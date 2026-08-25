'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';

/**
 * Curseur et lecture automatique de la relecture — cahier FR-080 et FR-082.
 *
 * Amélioration progressive au sens strict : le composant navigue entre les
 * **mêmes URL** `?at=` que les liens de la page, qui restent le parcours sans
 * JavaScript et l'alternative textuelle (FR-083, FR-085). Il n'introduit
 * aucun état que l'adresse ne porte pas — recharger, partager ou revenir en
 * arrière tombe toujours sur le même instant.
 *
 * Le **pas** est celui des passages satellitaires : la donnée n'existe qu'à
 * ces instants, un pas plus fin rejouerait du vide (FR-084). La **vitesse**
 * par défaut s'adapte à la durée : un feu de six jours à 570 observations ne
 * se rejoue pas au rythme d'un feu d'une nuit (FR-082).
 *
 * La lecture automatique est une animation : si le système demande la
 * réduction des animations, elle n'est pas proposée — le curseur et les
 * liens, statiques, rendent le même service.
 */

const SPEEDS = [1, 2, 4] as const;
const BASE_STEP_MS = 2000;

function defaultSpeed(instantCount: number): (typeof SPEEDS)[number] {
  if (instantCount > 40) return 4;
  if (instantCount > 15) return 2;
  return 1;
}

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function subscribeToReducedMotion(onStoreChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener('change', onStoreChange);
  return () => query.removeEventListener('change', onStoreChange);
}

function readReducedMotion(): boolean {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

// Côté serveur, la préférence est inconnue : on suppose l'animation permise,
// le client corrige à l'hydratation avant toute lecture.
function serverReducedMotion(): boolean {
  return false;
}

export function ReplayControls({
  basePath,
  instants,
  labels,
  currentIndex,
}: {
  basePath: string;
  /** Instants ISO des passages, ordonnés. */
  instants: string[];
  /** Les mêmes instants, formatés dans le fuseau de l'événement. */
  labels: string[];
  currentIndex: number;
}) {
  const router = useRouter();
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(() => defaultSpeed(instants.length));
  const reducedMotion = useSyncExternalStore(
    subscribeToReducedMotion,
    readReducedMotion,
    serverReducedMotion,
  );

  const index = currentIndex >= 0 ? currentIndex : 0;
  const atEnd = index >= instants.length - 1;
  // Au dernier passage, la lecture n'a plus rien à jouer : l'état demandé
  // reste, l'état effectif s'éteint — sans écrire d'état depuis un effet.
  const effectivePlaying = playing && !atEnd && !reducedMotion;

  const hrefFor = useMemo(
    () => (iso: string) => `${basePath}?at=${encodeURIComponent(iso)}`,
    [basePath],
  );

  // Un pas à la fois : chaque navigation ramène un nouvel index, qui
  // replanifie le suivant — le rythme absorbe l'aller-retour serveur au lieu
  // de s'empiler dessus.
  useEffect(() => {
    if (!effectivePlaying) return;
    const iso = instants[index + 1];
    if (iso === undefined) return;
    const timer = window.setTimeout(() => {
      router.replace(hrefFor(iso), { scroll: false });
    }, BASE_STEP_MS / speed);
    return () => window.clearTimeout(timer);
  }, [effectivePlaying, index, speed, instants, router, hrefFor]);

  if (instants.length < 2) return null;

  return (
    <div
      className="border-(--border) mt-6 rounded-md border p-4"
      role="group"
      aria-label="Lecture de la relecture"
    >
      <input
        type="range"
        min={0}
        max={instants.length - 1}
        value={index}
        onChange={(changeEvent) => {
          setPlaying(false);
          const iso = instants[Number(changeEvent.target.value)];
          if (iso !== undefined) {
            router.replace(hrefFor(iso), { scroll: false });
          }
        }}
        className="w-full"
        aria-label="Instant de la relecture"
        aria-valuetext={labels[index] ?? ''}
      />
      <div className="text-small mt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
        <span className="mono" aria-hidden="true">
          {labels[index]} · {index + 1}/{instants.length}
        </span>

        {reducedMotion ? (
          <span className="text-(--text-3)">
            Lecture automatique désactivée : votre système demande la réduction des animations.
          </span>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setPlaying(!effectivePlaying && !atEnd)}
              disabled={atEnd}
              className="font-semibold underline underline-offset-4 disabled:no-underline disabled:opacity-60"
            >
              {effectivePlaying ? 'Pause' : 'Lecture'}
            </button>
            <label className="text-(--text-2)">
              Vitesse{' '}
              <select
                value={speed}
                onChange={(changeEvent) =>
                  setSpeed(Number(changeEvent.target.value) as (typeof SPEEDS)[number])
                }
                className="border-(--border) rounded border bg-transparent px-1 py-0.5"
              >
                {SPEEDS.map((value) => (
                  <option key={value} value={value}>
                    ×{value}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
      </div>
    </div>
  );
}
