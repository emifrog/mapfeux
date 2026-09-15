import { CHART_HEIGHT, CHART_WIDTH, frpChartModel } from '@/lib/events/frp-chart';
import type { SatellitePass } from '@/lib/events/passes';

/**
 * Puissance radiative par passage — le graphique de la fiche.
 *
 * Référence : cahier §5.7, §6.5, FR-053.
 *
 * Rendu par le serveur, sans JavaScript : un SVG et quelques libellés.
 * La géométrie vient de `frpChartModel`, testée seule ; ici on ne fait que
 * poser des rectangles dans une boîte de mille sur cent que le navigateur
 * étire à la largeur disponible. Les libellés restent en HTML, hors de la
 * boîte, pour garder leur corps sur un téléphone.
 *
 * ## Une seule couleur, et c'est l'orange thermique
 *
 * La barre porte la couleur de l'observation thermique récente (§8.1) :
 * c'est de puissance radiative observée qu'il s'agit, le seul propos
 * auquel l'orange appartient. Les passages de nuit sont plus sombres, et
 * dits — jamais la nuance seule.
 *
 * Chaque barre porte un `<title>` : au survol, le passage se lit en clair
 * — heure, satellite, nombre d'observations, puissance. C'est une aide,
 * pas le seul accès : le tableau des observations dit tout, en texte.
 */

const TIME = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'Europe/Paris',
});

const MW = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

function passLabel(pass: SatellitePass, timeZone: string): string {
  const time = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone,
  }).format(pass.at);
  const period = pass.dayNight === 'D' ? ' · jour' : pass.dayNight === 'N' ? ' · nuit' : '';
  const power =
    pass.frpTotalMw === null ? 'puissance non disponible' : `${MW.format(pass.frpTotalMw)} MW`;
  return `${time} · ${pass.satellite} (${pass.sensor})${period} · ${pass.pixels} observation${
    pass.pixels > 1 ? 's' : ''
  } · ${power}`;
}

export function FrpChart({
  passes,
  timeZone = 'Europe/Paris',
}: {
  passes: readonly SatellitePass[];
  timeZone?: string;
}) {
  const model = frpChartModel(passes);
  if (model === null) return null;

  const format = timeZone === 'Europe/Paris' ? TIME : undefined;
  const at = (date: Date): string =>
    (
      format ??
      new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'short', timeZone })
    ).format(date);

  const peak = model.bars.reduce<SatellitePass | null>(
    (best, bar) =>
      bar.pass.frpTotalMw !== null &&
      (best === null || bar.pass.frpTotalMw > (best.frpTotalMw ?? 0))
        ? bar.pass
        : best,
    null,
  );

  const summary = `Puissance radiative par passage : ${passes.length} passages du ${at(
    model.span.from,
  )} au ${at(model.span.to)}${
    peak === null ? '' : `, maximum ${MW.format(peak.frpTotalMw ?? 0)} MW le ${at(peak.at)}`
  }.`;

  return (
    <figure className="mt-6">
      <figcaption className="text-small flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-semibold">Puissance radiative par passage</span>
        <span className="text-(--text-3)">
          somme des observations d’un même passage, en mégawatts
        </span>
      </figcaption>

      <div className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        {/* L'axe vertical en HTML : ses chiffres ne rétrécissent pas avec
            la boîte. Trois graduations — zéro, milieu, plafond —, alignées
            sur les filets du SVG par la même répartition. */}
        <div
          className="mono text-label text-(--text-3) flex flex-col justify-between text-right"
          style={{ height: '10rem' }}
          aria-hidden="true"
        >
          {[...model.yTicks].reverse().map((tick) => (
            <span key={tick.value} className="leading-none">
              {MW.format(tick.value)}
            </span>
          ))}
        </div>

        <div>
          <svg
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            preserveAspectRatio="none"
            className="block w-full"
            style={{ height: '10rem' }}
            role="img"
            aria-label={summary}
          >
            {model.yTicks.map((tick) => (
              <line
                key={tick.value}
                x1={0}
                x2={CHART_WIDTH}
                y1={tick.y}
                y2={tick.y}
                stroke="var(--border)"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {model.bars.map((bar) => (
              <g key={`${bar.pass.satellite}-${bar.pass.at.toISOString()}`}>
                <title>{passLabel(bar.pass, timeZone)}</title>
                {bar.known ? (
                  <rect
                    x={bar.x}
                    y={bar.y}
                    width={bar.width}
                    height={Math.max(bar.height, 0.8)}
                    fill="var(--color-age-2)"
                    opacity={bar.pass.dayNight === 'N' ? 0.7 : 1}
                  />
                ) : (
                  // Sans puissance connue : une marque au sol, creuse — le
                  // passage a eu lieu, sa puissance n'est pas connue.
                  <rect
                    x={bar.x}
                    y={CHART_HEIGHT - 3}
                    width={bar.width}
                    height={3}
                    fill="none"
                    stroke="var(--text-3)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
              </g>
            ))}
          </svg>

          <div className="mono text-label text-(--text-3) mt-1.5 flex justify-between gap-4">
            <span>{at(model.span.from)}</span>
            <span>{at(model.span.to)}</span>
          </div>
        </div>
      </div>

      <p className="text-small text-(--text-2) mt-3 max-w-[68ch]">
        Les barres pleines sont des passages de jour, les barres atténuées des passages de nuit ;
        une marque creuse au sol est un passage dont la puissance n’est pas connue. Survoler une
        barre l’énonce en clair ; le tableau ci-dessous dit tout, observation par observation.
      </p>
    </figure>
  );
}
