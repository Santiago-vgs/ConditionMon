import { useId, useMemo, useState } from "react";
import {
  MAINTENANCE_THRESHOLD,
  RUL_MAX,
  STATUS,
  TAU,
  WARNING_THRESHOLD,
} from "../config";

// Predicted RUL over an engine's whole life, drawn as raw SVG — the fleet is
// 100 engines of at most ~300 points, so a charting library would be more
// bundle than the entire app for one view.
//
// What's on it, in reading order:
//   · the 90% conformal interval as a neutral filled band — the honest width of
//     the estimate, which narrows as the engine approaches failure
//   · predicted RUL, stroked with a gradient that changes at the maintenance
//     and warning thresholds. The status is a property of where the line *is*,
//     not of the engine as a whole: painting the whole series in today's status
//     colour would make an engine that just entered maintenance look like it had
//     been failing since cycle 1
//   · actual RUL, dashed. FD001 ships true end-of-life for the test set, so this
//     is a genuine predicted-vs-actual overlay, not a smoothing of one series
//   · τ, the cost-optimal alert threshold — the line that should have triggered
//     the work order

const W = 640;
const H = 300;
const PAD = { top: 16, right: 16, bottom: 34, left: 40 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

// Gradient offsets run top (RUL_MAX) to bottom (0); doubling each stop makes the
// colour change abruptly at the threshold instead of fading across it.
const stopAt = (rul) => 1 - rul / RUL_MAX;
const GRADIENT_STOPS = [
  { offset: 0, color: STATUS.OK.color },
  { offset: stopAt(WARNING_THRESHOLD), color: STATUS.OK.color },
  { offset: stopAt(WARNING_THRESHOLD), color: STATUS.WARNING.color },
  { offset: stopAt(MAINTENANCE_THRESHOLD), color: STATUS.WARNING.color },
  { offset: stopAt(MAINTENANCE_THRESHOLD), color: STATUS.MAINTENANCE_REQUIRED.color },
  { offset: 1, color: STATUS.MAINTENANCE_REQUIRED.color },
];

// Which status band a RUL value falls in — mirrors status_for() in train.py.
function zoneColor(rul) {
  if (rul < MAINTENANCE_THRESHOLD) return STATUS.MAINTENANCE_REQUIRED.color;
  if (rul < WARNING_THRESHOLD) return STATUS.WARNING.color;
  return STATUS.OK.color;
}

export default function DegradationChart({ points, label }) {
  const [hover, setHover] = useState(null);
  const gradientId = useId(); // two charts on one page must not share a <defs> id

  const { x, y, predPath, actualPath, bandPath, xTicks, yTicks } = useMemo(() => {
    const maxCycle = Math.max(...points.map((p) => p.cycle));
    const x = (cycle) => PAD.left + (cycle / maxCycle) * PLOT_W;
    const y = (rul) => PAD.top + (1 - Math.min(rul, RUL_MAX) / RUL_MAX) * PLOT_H;

    const line = (key) =>
      points.map((p, i) => `${i ? "L" : "M"}${x(p.cycle)},${y(p[key])}`).join(" ");

    // upper edge left-to-right, lower edge back right-to-left, closed
    const upper = points.map((p) => `${x(p.cycle)},${y(p.rul_high)}`);
    const lower = [...points].reverse().map((p) => `${x(p.cycle)},${y(p.rul_low)}`);

    return {
      x,
      y,
      predPath: line("predicted_rul"),
      actualPath: line("actual_rul"),
      bandPath: `M${upper.join(" L")} L${lower.join(" L")} Z`,
      xTicks: tickValues(maxCycle),
      yTicks: [0, 30, 60, 90, 125],
    };
  }, [points]);

  // Pointer x -> nearest sample. Coordinates come back in viewBox units because
  // the SVG scales with the container, so the ratio has to be applied by hand.
  const onMove = (ev) => {
    const rect = ev.currentTarget.getBoundingClientRect();
    const svgX = ((ev.clientX - rect.left) / rect.width) * W;
    let best = points[0];
    let bestDist = Infinity;
    for (const p of points) {
      const d = Math.abs(x(p.cycle) - svgX);
      if (d < bestDist) [best, bestDist] = [p, d];
    }
    setHover(best);
  };

  const active = hover ?? points[points.length - 1];

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        aria-label={`Predicted remaining useful life over ${points.length} cycles for ${label}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient
            id={gradientId}
            gradientUnits="userSpaceOnUse"
            x1="0"
            y1={PAD.top}
            x2="0"
            y2={PAD.top + PLOT_H}
          >
            {GRADIENT_STOPS.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
        </defs>

        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={PAD.left + PLOT_W}
              y1={y(t)}
              y2={y(t)}
              className="chart-grid"
            />
            <text x={PAD.left - 8} y={y(t) + 4} className="chart-tick chart-tick-y">
              {t}
            </text>
          </g>
        ))}

        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={H - 12} className="chart-tick chart-tick-x">
            {t}
          </text>
        ))}

        <path d={bandPath} className="chart-band" />
        <path d={actualPath} className="chart-actual" />
        <path
          d={predPath}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />

        <line
          x1={PAD.left}
          x2={PAD.left + PLOT_W}
          y1={y(TAU)}
          y2={y(TAU)}
          className="chart-tau"
        />
        <text x={PAD.left + 6} y={y(TAU) - 5} className="chart-tau-label">
          alert τ = {TAU}
        </text>

        {hover && (
          <g>
            <line
              x1={x(hover.cycle)}
              x2={x(hover.cycle)}
              y1={PAD.top}
              y2={PAD.top + PLOT_H}
              className="chart-crosshair"
            />
            <circle
              cx={x(hover.cycle)}
              cy={y(hover.predicted_rul)}
              r="4"
              fill={zoneColor(hover.predicted_rul)}
            />
          </g>
        )}
      </svg>

      <figcaption className="chart-readout">
        <span className="chart-readout-cycle">Cycle {active.cycle}</span>
        <Readout
          label="Predicted"
          value={active.predicted_rul}
          color={zoneColor(active.predicted_rul)}
        />
        <Readout label="Range" value={`${active.rul_low}–${active.rul_high}`} />
        <Readout label="Actual" value={active.actual_rul} />
      </figcaption>

      <p className="chart-legend">
        Solid line is the model’s estimate — it turns amber under {WARNING_THRESHOLD} cycles
        and red under {MAINTENANCE_THRESHOLD}. Shaded band is the 90% interval, dashed line
        the true remaining life. Hover to read any cycle.
      </p>
    </figure>
  );
}

function Readout({ label, value, color }) {
  return (
    <span className="chart-readout-item">
      <span className="chart-readout-label">{label}</span>
      <span className="chart-readout-value" style={color ? { color } : undefined}>
        {value}
      </span>
    </span>
  );
}

// Round tick spacing so labels land on 25s/50s/100s rather than arbitrary cycles.
function tickValues(maxCycle) {
  const step = maxCycle > 240 ? 100 : maxCycle > 120 ? 50 : 25;
  const ticks = [];
  for (let t = 0; t <= maxCycle; t += step) ticks.push(t);
  return ticks;
}
