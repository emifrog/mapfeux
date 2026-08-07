'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

/**
 * « Autour de moi » — ouvre la commune où se trouve l'utilisateur.
 *
 * Référence : cahier §5.3 (FR-020 à FR-024) et §22.2.
 *
 * La permission n'est demandée qu'au clic, jamais au chargement (FR-020). La
 * position ne quitte le navigateur qu'arrondie à la troisième décimale —
 * environ cent mètres, assez pour résoudre une commune, pas pour désigner une
 * adresse (§22.2) — et voyage en corps de requête POST, jamais en URL. Le
 * composant ne conserve que le statut du parcours : les coordonnées ne sont ni
 * stockées ni journalisées (FR-022). Un refus laisse la recherche par nom
 * intacte, et le dit (FR-023).
 */

type Status = 'idle' | 'working' | 'error';

const REFUSAL_MESSAGE = 'La géolocalisation a été refusée. La recherche par nom reste utilisable.';
const UNAVAILABLE_MESSAGE =
  'Position indisponible pour le moment. La recherche par nom reste utilisable.';

// ~110 m : la précision maximale utile à une résolution communale.
function rounded(value: number): number {
  return Math.round(value * 1000) / 1000;
}

export function NearMe() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  function fail(text: string) {
    setStatus('error');
    setMessage(text);
  }

  async function resolve(longitude: number, latitude: number) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch('/api/v1/location/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ longitude: rounded(longitude), latitude: rounded(latitude) }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          error?: { message?: string };
        } | null;
        fail(payload?.error?.message ?? UNAVAILABLE_MESSAGE);
        return;
      }

      const payload = (await response.json()) as { data: { insee: string } };
      router.push(`/communes/${payload.data.insee}`);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      fail(UNAVAILABLE_MESSAGE);
    }
  }

  function locate() {
    setMessage(null);

    if (!('geolocation' in navigator)) {
      fail(
        'Ce navigateur ne fournit pas de géolocalisation. La recherche par nom reste utilisable.',
      );
      return;
    }

    setStatus('working');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void resolve(position.coords.longitude, position.coords.latitude);
      },
      (error) => {
        fail(error.code === error.PERMISSION_DENIED ? REFUSAL_MESSAGE : UNAVAILABLE_MESSAGE);
      },
      // Précision réduite : la commune n'a pas besoin du GPS fin, et le
      // demander allonge l'attente autant qu'il affine inutilement (§22.2).
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  }

  return (
    <span>
      <button
        type="button"
        onClick={locate}
        disabled={status === 'working'}
        aria-busy={status === 'working'}
        className="font-semibold underline underline-offset-4 disabled:opacity-60"
      >
        Autour de moi
      </button>

      {/* Les changements d'état sont annoncés sans voler le focus. */}
      <span className="sr-only" role="status" aria-live="polite">
        {status === 'working' && 'Recherche de votre commune en cours'}
      </span>

      {status === 'working' && (
        <span aria-hidden="true" className="text-(--text-2) ml-3">
          Recherche de votre commune…
        </span>
      )}

      {message !== null && (
        <span role="alert" className="text-small text-(--text-2) mt-2 block max-w-[48ch]">
          {message}
        </span>
      )}
    </span>
  );
}
