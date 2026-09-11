'use client';

import { POLLUTANT_LABELS } from '@/lib/air/labels';
import type { RadarTimeline } from '@/lib/radar/timeline';

import type { AirTilesInfo } from './air-layer';

/**
 * Panneau de calques, posé sur la carte. Cahier §19.1, §19.3, FR-121.
 *
 * Les calques se groupent par famille — ce qui est observé d'un côté, ce qui
 * est modélisé de l'autre — parce que la distinction est de fond : une
 * détection thermique et une grille de prévision ne s'éteignent pas pour les
 * mêmes raisons, et le lecteur doit voir laquelle il regarde. L'observation
 * n'a pas d'interrupteur : c'est le sujet de la carte, pas une option.
 *
 * Le panneau porte les **commandes** et l'échelle de la couche active. Les
 * explications — provenance, run, heure de validité, avertissements — vivent
 * sous la carte : elles se lisent, elles ne se manipulent pas, et les loger
 * ici prenait la place des commandes (le défaut corrigé le 11 septembre).
 */

interface Band {
  jusqu_a: number | null;
  couleur: string;
  libelle: string;
}

/** « ≤ 20 », « 20–40 », « > 150 » — les bornes viennent de la palette servie. */
function bandRange(bands: Band[], index: number): string {
  const upper = bands[index]?.jusqu_a ?? null;
  const previous = index > 0 ? (bands[index - 1]?.jusqu_a ?? null) : null;
  if (previous === null) return `≤ ${upper ?? '∞'}`;
  if (upper === null) return `> ${previous}`;
  return `${previous}–${upper}`;
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-3 first:mt-0">
      <h3
        className="mb-1.5 text-[9.5px] font-medium uppercase tracking-[0.08em]"
        style={{ color: 'var(--text-3)' }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

function Choices<T extends string | null | boolean>({
  name,
  legend,
  choices,
  label,
  current,
  onChange,
}: {
  name: string;
  legend: string;
  choices: readonly T[];
  label: (choice: T) => string;
  current: T;
  onChange: (choice: T) => void;
}) {
  return (
    <fieldset>
      <legend className="sr-only">{legend}</legend>
      <div className="flex flex-wrap gap-1">
        {choices.map((choice) => (
          <label
            key={String(choice)}
            className="cursor-pointer rounded-md border px-2 py-[3px]"
            style={{
              borderColor: current === choice ? 'var(--border-strong)' : 'var(--border)',
              background: current === choice ? 'var(--surface-muted)' : 'transparent',
              color: current === choice ? 'var(--text)' : 'var(--text-2)',
            }}
          >
            <input
              type="radio"
              name={name}
              className="sr-only"
              checked={current === choice}
              onChange={() => onChange(choice)}
            />
            {label(choice)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Scale({ bands, unit }: { bands: Band[]; unit: string }) {
  return (
    <ul className="mt-2 flex flex-col gap-1">
      {bands.map((band, index) => (
        <li key={band.libelle} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="rounded-xs block size-2 shrink-0"
            style={{ backgroundColor: band.couleur }}
          />
          <span className="w-14 tabular-nums">{bandRange(bands, index)}</span>
          <span className="font-sans text-[11px]">{band.libelle}</span>
        </li>
      ))}
      <li className="tabular-nums" style={{ color: 'var(--text-3)' }}>
        en {unit}
      </li>
    </ul>
  );
}

const POLLUTANTS = [null, 'pm2_5', 'pm10'] as const;
const RADAR = [false, true] as const;

export interface LayersPanelProps {
  pollutant: string | null;
  onPollutant: (pollutant: string | null) => void;
  airInfo: AirTilesInfo | null;
  airMissing: boolean;
  radarOn: boolean;
  onRadarOn: (on: boolean) => void;
  radarTimeline: RadarTimeline | null;
  radarMissing: boolean;
  radarIndex: number;
  onRadarIndex: (index: number) => void;
  playing: boolean;
  onPlaying: (playing: boolean) => void;
  reducedMotion: boolean;
  timeFormat: Intl.DateTimeFormat;
}

export function LayersPanel({
  pollutant,
  onPollutant,
  airInfo,
  airMissing,
  radarOn,
  onRadarOn,
  radarTimeline,
  radarMissing,
  radarIndex,
  onRadarIndex,
  playing,
  onPlaying,
  reducedMotion,
  timeFormat,
}: LayersPanelProps) {
  const currentFrame = radarTimeline?.frames[radarIndex];

  return (
    <section
      aria-labelledby="calques"
      className="mono rounded-xl border p-3 text-[11px] shadow-lg max-sm:mt-3 sm:absolute sm:right-3 sm:top-3 sm:z-10 sm:max-h-[calc(100%-1.5rem)] sm:w-64 sm:overflow-y-auto"
      style={{
        background: 'color-mix(in srgb, var(--surface) 92%, transparent)',
        borderColor: 'var(--border)',
        color: 'var(--text-2)',
        backdropFilter: 'blur(6px)',
      }}
    >
      <h2
        id="calques"
        className="mb-2 text-[9.5px] font-medium uppercase tracking-[0.08em]"
        style={{ color: 'var(--text)' }}
      >
        Calques de la carte
      </h2>

      <Group title="Observation">
        {/* Pas d'interrupteur : les détections sont le sujet de la carte. */}
        <p className="font-sans text-[11px] leading-snug">
          Détections thermiques et événements, toujours affichés.
        </p>
      </Group>

      <Group title="Atmosphère">
        <p className="font-sans text-[11px] leading-snug">Qualité de l’air modélisée</p>
        <div className="mt-1">
          <Choices
            name="couche-air"
            legend="Couche de qualité de l’air affichée"
            choices={POLLUTANTS}
            current={pollutant}
            onChange={onPollutant}
            label={(choice) => (choice === null ? 'Sans' : (POLLUTANT_LABELS[choice] ?? choice))}
          />
        </div>
        <div aria-live="polite">
          {airMissing && (
            <p className="mt-2 font-sans text-[11px] leading-snug">
              Aucune donnée modélisée récente.
            </p>
          )}
          {airInfo !== null && <Scale bands={airInfo.bands} unit={airInfo.unit} />}
        </div>
      </Group>

      <Group title="Précipitations">
        <p className="font-sans text-[11px] leading-snug">Radar, lame d’eau</p>
        <div className="mt-1">
          <Choices
            name="couche-radar"
            legend="Couche radar affichée"
            choices={RADAR}
            current={radarOn}
            onChange={onRadarOn}
            label={(choice) => (choice ? 'Lame d’eau' : 'Sans')}
          />
        </div>
        <div aria-live="polite">
          {radarMissing && (
            <p className="mt-2 font-sans text-[11px] leading-snug">Aucune frame récente.</p>
          )}
          {radarTimeline !== null && currentFrame !== undefined && (
            <>
              {/* FR-123 : la frame et son heure d'acquisition, toujours. */}
              <p className="mt-2 tabular-nums">
                {radarIndex + 1}/{radarTimeline.frames.length} · acquise à{' '}
                <time dateTime={currentFrame.acquiredAt.toISOString()}>
                  {timeFormat.format(currentFrame.acquiredAt)}
                </time>
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                <button
                  type="button"
                  className="rounded-md border px-2 py-[3px]"
                  style={{ borderColor: 'var(--border)' }}
                  onClick={() => {
                    onPlaying(false);
                    onRadarIndex(
                      (radarIndex - 1 + radarTimeline.frames.length) % radarTimeline.frames.length,
                    );
                  }}
                  aria-label="Frame précédente"
                >
                  ◀
                </button>
                <button
                  type="button"
                  className="rounded-md border px-2 py-[3px]"
                  style={{ borderColor: 'var(--border)' }}
                  onClick={() => {
                    onPlaying(false);
                    onRadarIndex((radarIndex + 1) % radarTimeline.frames.length);
                  }}
                  aria-label="Frame suivante"
                >
                  ▶
                </button>
                {/* La lecture automatique n'existe pas quand la réduction des
                    animations est demandée ; le pas-à-pas, si (§19.3). */}
                {!reducedMotion && radarTimeline.frames.length > 1 && (
                  <button
                    type="button"
                    className="rounded-md border px-2 py-[3px]"
                    style={{
                      borderColor: playing ? 'var(--border-strong)' : 'var(--border)',
                      background: playing ? 'var(--surface-muted)' : 'transparent',
                    }}
                    onClick={() => onPlaying(!playing)}
                  >
                    {playing ? '⏸ pause' : '▶ lecture'}
                  </button>
                )}
              </div>
              <Scale bands={radarTimeline.bands} unit={radarTimeline.unit} />
            </>
          )}
        </div>
      </Group>
    </section>
  );
}
