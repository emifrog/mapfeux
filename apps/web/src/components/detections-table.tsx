import { CONFIDENCE_LEVEL_LABELS } from '@mapfeux/ui';

import type { EventDetection } from '@/lib/data/events';

/**
 * Le tableau des observations membres — alternative textuelle à la carte.
 *
 * Référence : cahier §8.6, FR-051.
 *
 * ## Douze lignes, puis un pli
 *
 * Cinquante-sept observations font deux mille trois cents pixels de tableau,
 * et tout ce qui vient après — localisation, périmètres, partage — tombait
 * quatre écrans plus bas. Constaté le 15 septembre 2026 sur
 * Condé-sur-l'Escaut. Les douze plus récentes s'affichent ; les autres
 * sont sous un `<details>` natif, replié, qui dit combien il en cache.
 *
 * Rien n'est masqué au sens du cahier : tout est dans la page, rendu par
 * le serveur, et s'ouvre sans JavaScript. Le pli est un repli de lecture,
 * pas une omission — et il annonce son compte.
 */

export const VISIBLE_DETECTIONS = 12;

function formatInstant(value: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone,
  }).format(value);
}

function Rows({ detections, timeZone }: { detections: EventDetection[]; timeZone: string }) {
  return (
    <>
      {detections.map((detection, index) => (
        // L'heure et la longitude ne suffisent pas : deux pixels d'un même
        // passage partagent les deux — vu sur Pontevès. La liste est triée
        // et rendue serveur, l'indice est stable.
        <tr
          key={`${detection.acquiredAt.toISOString()}-${index}`}
          className="border-(--border) border-b"
        >
          <td className="py-2 pr-4">
            <time dateTime={detection.acquiredAt.toISOString()}>
              {formatInstant(detection.acquiredAt, timeZone)}
            </time>
          </td>
          <td className="py-2 pr-4">
            {detection.sensor} · {detection.satellite}
            {detection.dayNight !== null && (
              <span className="text-(--text-2)">
                {detection.dayNight === 'D' ? ' · jour' : ' · nuit'}
              </span>
            )}
          </td>
          <td className="py-2 pr-4">
            {detection.confidenceLevel === 'unknown'
              ? 'Inconnue'
              : CONFIDENCE_LEVEL_LABELS[detection.confidenceLevel]}
          </td>
          <td className="py-2">{detection.frpMw === null ? '—' : `${detection.frpMw} MW`}</td>
        </tr>
      ))}
    </>
  );
}

function Table({
  detections,
  timeZone,
  caption,
}: {
  detections: EventDetection[];
  timeZone: string;
  caption: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-xl w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-(--border-strong) border-b-2">
            <th scope="col" className="py-2 pr-4">
              Heure d’acquisition
            </th>
            <th scope="col" className="py-2 pr-4">
              Capteur
            </th>
            <th scope="col" className="py-2 pr-4">
              Confiance
            </th>
            <th scope="col" className="py-2">
              FRP
            </th>
          </tr>
        </thead>
        <tbody>
          <Rows detections={detections} timeZone={timeZone} />
        </tbody>
      </table>
    </div>
  );
}

export function DetectionsTable({
  detections,
  timeZone,
  visibleLimit = VISIBLE_DETECTIONS,
}: {
  /** De la plus récente à la plus ancienne. */
  detections: EventDetection[];
  timeZone: string;
  visibleLimit?: number;
}) {
  const visible = detections.slice(0, visibleLimit);
  const folded = detections.slice(visibleLimit);

  return (
    <div className="mt-4">
      <Table
        detections={visible}
        timeZone={timeZone}
        caption={
          folded.length === 0
            ? 'Observations satellitaires rattachées à cet événement, de la plus récente à la plus ancienne'
            : `Les ${visible.length} observations les plus récentes, sur ${detections.length}`
        }
      />

      {folded.length > 0 && (
        <details className="mt-3">
          <summary className="text-small cursor-pointer font-semibold underline underline-offset-4">
            Les {folded.length} observation{folded.length > 1 ? 's' : ''} plus ancienne
            {folded.length > 1 ? 's' : ''}
          </summary>
          <div className="mt-3">
            <Table
              detections={folded}
              timeZone={timeZone}
              caption={`Les ${folded.length} observations plus anciennes, de la plus récente à la plus ancienne`}
            />
          </div>
        </details>
      )}
    </div>
  );
}
