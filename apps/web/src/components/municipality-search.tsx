'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useId, useRef, useState } from 'react';

/**
 * Recherche de commune.
 *
 * Référence : cahier §5.3 (FR-020, FR-021, FR-026) et §6.5.
 *
 * Motif ARIA combobox : la liste est annoncée, parcourable au clavier et
 * l'option active est liée au champ par `aria-activedescendant`. La recherche
 * reste pleinement fonctionnelle sans souris, ce que le §6.5 exige des parcours
 * principaux.
 */

interface Result {
  insee: string;
  name: string;
  departmentCode: string;
  postalCodes: string[];
}

const DEBOUNCE_MS = 250;
const MIN_QUERY_LENGTH = 2;

export function MunicipalitySearch({ autoFocus = false }: { autoFocus?: boolean }) {
  const router = useRouter();
  const listboxId = useId();
  const optionIdPrefix = useId();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');

  const abortRef = useRef<AbortController | null>(null);

  const trimmed = query.trim();
  // Dérivé plutôt que stocké : remettre l'état à zéro depuis l'effet
  // provoquerait un rendu en cascade à chaque frappe.
  const isQueryLongEnough = trimmed.length >= MIN_QUERY_LENGTH;

  useEffect(() => {
    if (!isQueryLongEnough) {
      // Une requête devenue trop courte n'a plus d'intérêt : on abandonne
      // celle qui est en vol plutôt que de la laisser écrire un résultat
      // que l'on n'affichera pas.
      abortRef.current?.abort();
      return;
    }

    const timer = setTimeout(() => {
      // Une frappe rapide annule la requête précédente : sans cela, une réponse
      // lente peut écraser une réponse plus récente.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setStatus('loading');

      fetch(`/api/v1/municipalities/search?q=${encodeURIComponent(trimmed)}`, {
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error(String(response.status));
          return response.json();
        })
        .then((payload: { data: Result[] }) => {
          setResults(payload.data);
          setActiveIndex(-1);
          setIsOpen(true);
          setStatus('idle');
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === 'AbortError') return;
          setResults([]);
          setStatus('error');
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [trimmed, isQueryLongEnough]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function select(result: Result) {
    setIsOpen(false);
    router.push(`/commune/${result.insee}`);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setIsOpen(false);
      return;
    }
    if (results.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => (index + 1) % results.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1));
    } else if (event.key === 'Enter') {
      const target = results[activeIndex] ?? results[0];
      if (target !== undefined) {
        event.preventDefault();
        select(target);
      }
    }
  }

  // La longueur de la saisie conditionne l'affichage : les résultats d'une
  // recherche précédente ne doivent pas survivre à un champ vidé.
  const showList = isOpen && isQueryLongEnough && results.length > 0;
  const showError = status === 'error' && isQueryLongEnough;

  return (
    <div className="relative">
      <label htmlFor={`${optionIdPrefix}-input`} className="block text-sm font-medium">
        Rechercher une commune
      </label>

      <input
        id={`${optionIdPrefix}-input`}
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={
          activeIndex >= 0 ? `${optionIdPrefix}-option-${activeIndex}` : undefined
        }
        autoComplete="off"
        autoFocus={autoFocus}
        value={query}
        placeholder="Nom de commune ou code postal"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => isQueryLongEnough && results.length > 0 && setIsOpen(true)}
        className="border-(--border-strong) mt-1 w-full rounded border px-3 py-2 text-base"
      />

      {/* Les changements d'état sont annoncés sans voler le focus. */}
      <p className="sr-only" role="status" aria-live="polite">
        {status === 'loading' && isQueryLongEnough && 'Recherche en cours'}
        {showError && 'La recherche est indisponible'}
        {status === 'idle' &&
          showList &&
          `${results.length} commune${results.length > 1 ? 's' : ''} trouvée${results.length > 1 ? 's' : ''}`}
      </p>

      {showError && (
        <p className="text-(--text-2) mt-2 text-sm">
          La recherche est momentanément indisponible. Vous pouvez consulter un département depuis
          la page d’accueil.
        </p>
      )}

      {showList && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Communes correspondantes"
          className="border-(--border-strong) absolute z-10 mt-1 w-full overflow-hidden rounded border bg-white shadow-lg"
        >
          {results.map((result, index) => (
            <li
              key={result.insee}
              id={`${optionIdPrefix}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              // Le pointeur sert la souris ; le clavier passe par onKeyDown.
              onMouseDown={(event) => {
                event.preventDefault();
                select(result);
              }}
              onMouseEnter={() => setActiveIndex(index)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                index === activeIndex ? 'bg-(--surface-muted)' : ''
              }`}
            >
              <span className="font-medium">{result.name}</span>{' '}
              {/* Le département lève les homonymes. FR-021 */}
              <span className="text-(--text-2)">({result.departmentCode})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
