import { useMemo, useState } from "react";
import { MAINTENANCE_THRESHOLD, RAMP, TAU } from "../config";

// Expected cost per engine against the alert threshold τ, one curve per
// assumption about how much an unscheduled failure costs relative to a
// scheduled visit. The point of showing all three: they diverge sharply below
// τ≈23 and lie on top of each other above it, because past that threshold no
// failure is missed and the failure cost stops mattering. The optimum is
// therefore robust to the assumption — which is the actual finding, and is only
// visible if the curves are drawn rather than summarised to one number.
//
// Ordinal ramp, not categorical: 10 < 50 < 100 is an ordered quantity.

const W = 680;
const H = 300;
const PAD = { top: 18, right: 18, bottom: 46, left: 58 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

export default function CostSweepChart({ taus, ratios }) {
  const [hoverIdx, setHoverIdx] = useState(null);

  const series = useMemo(
    () =>
      Object.entries(ratios)
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map(([ratio, r], i) => ({ ratio, ...r, color: RAMP[i] ?? RAMP.at(-1) })),
    [ratios]
  );

  const { x, y, paths, yTicks } = useMemo(() => {
    const maxCost = Math.max(...series.flatMap((s) => s.curve));
    const x = (t) =>
      PAD.left + ((t - taus[0]) / (taus.at(-1) - taus[0])) * PLOT_W;
    const y = (c) => PAD.top + (1 - c / maxCost) * PLOT_H;
    const paths = series.map((s) => ({
      ...s,
      d: s.curve
        .map((c, i) => `${i ? "L" : "M"}${x(taus[i])},${y(c)}`)
        .join(" "),
    }));
    const step = Math.ceil(maxCost / 4);
    const yTicks = Array.from({ length: 5 }, (_, i) => i * step).filter(
      (t) => t <= maxCost
    );
    return { x, y, paths, yTicks };
  }, [series, taus]);

  const onMove = (ev) => {
    const rect = ev.currentTarget.getBoundingClientRect();
    const svgX = ((ev.clientX - rect.left) / rect.width) * W;
    let best = 0;
    let bestDist = Infinity;
    taus.forEach((t, i) => {
      const d = Math.abs(x(t) - svgX);
      if (d < bestDist) [best, bestDist] = [i, d];
    });
    setHoverIdx(best);
  };

  const readoutIdx = hoverIdx ?? taus.indexOf(TAU);

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart-svg"
        role="img"
        aria-label="Expected cost per engine against alert threshold, for three failure-cost ratios"
        onMouseMove={onMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
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

        {[10, 23, 40, 60, 80].map((t) => (
          <text key={t} x={x(t)} y={H - 14} className="chart-tick chart-tick-x">
            {t}
          </text>
        ))}
        <text x={PAD.left + PLOT_W / 2} y={H - 1} className="chart-axis-title">
          alert threshold τ (predicted RUL, cycles)
        </text>
        <text
          className="chart-axis-title"
          transform={`rotate(-90) translate(${-(PAD.top + PLOT_H / 2)} 11)`}
        >
          cost per engine (visits)
        </text>

        {/* the chosen threshold, and the status band it sits inside */}
        <line
          x1={x(TAU)}
          x2={x(TAU)}
          y1={PAD.top}
          y2={PAD.top + PLOT_H}
          className="chart-tau"
        />
        <text x={x(TAU) + 6} y={PAD.top + 12} className="chart-tau-label">
          τ = {TAU} (chosen)
        </text>
        <text
          x={x(MAINTENANCE_THRESHOLD) + 6}
          y={PAD.top + 28}
          className="chart-tau-label"
        >
          30 = old rule
        </text>
        <line
          x1={x(MAINTENANCE_THRESHOLD)}
          x2={x(MAINTENANCE_THRESHOLD)}
          y1={PAD.top}
          y2={PAD.top + PLOT_H}
          className="chart-tau faint"
        />

        {paths.map((s) => (
          <path key={s.ratio} d={s.d} fill="none" stroke={s.color} strokeWidth="2" />
        ))}

        {hoverIdx != null && (
          <>
            <line
              x1={x(taus[hoverIdx])}
              x2={x(taus[hoverIdx])}
              y1={PAD.top}
              y2={PAD.top + PLOT_H}
              className="chart-crosshair"
            />
            {series.map((s) => (
              <circle
                key={s.ratio}
                cx={x(taus[hoverIdx])}
                cy={y(s.curve[hoverIdx])}
                r="4"
                fill={s.color}
                className="chart-dot"
              />
            ))}
          </>
        )}
      </svg>

      <figcaption className="chart-readout">
        <span className="chart-readout-cycle">τ = {taus[readoutIdx]}</span>
        {series.map((s) => (
          <span className="chart-readout-item" key={s.ratio}>
            <span className="legend-swatch" style={{ background: s.color }} />
            <span className="chart-readout-label">{s.ratio}×</span>
            <span className="chart-readout-value">
              {s.curve[readoutIdx].toFixed(2)}
            </span>
          </span>
        ))}
      </figcaption>

      <p className="chart-legend">
        Cost in scheduled-maintenance visits per engine, for a failure costing
        10×, 50× or 100× a visit. Above τ≈{TAU} the three curves coincide — no
        failure is missed there, so the failure cost stops mattering and the
        optimum holds whichever assumption you make. Hover to read any τ.
      </p>
    </figure>
  );
}
