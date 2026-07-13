import { STATUS, RUL_MAX } from "../config";

// One soft white card per engine: name, status pill, the RUL figure, and a thin
// rounded progress bar coloured by status. The lighter band on the bar is the
// 90% prediction interval — how far off the estimate could plausibly be.
export default function FleetGrid({ engines, onSelect, selectedId }) {
  return (
    <div className="fleet-grid">
      {engines.map((e) => {
        const meta = STATUS[e.status] ?? STATUS.OK;
        const selected = e.engine_id === selectedId;
        const pct = Math.min(100, (e.predicted_rul / RUL_MAX) * 100);
        const lowPct = Math.min(100, ((e.rul_low ?? e.predicted_rul) / RUL_MAX) * 100);
        const highPct = Math.min(100, ((e.rul_high ?? e.predicted_rul) / RUL_MAX) * 100);
        return (
          <button
            key={e.engine_id}
            className={`card${selected ? " selected" : ""}`}
            onClick={() => onSelect(e)}
          >
            <div className="card-top">
              <span className="card-name">Engine {e.engine_id}</span>
              <span
                className="pill"
                style={{ color: meta.color, background: meta.tint }}
              >
                {meta.label}
              </span>
            </div>

            <div className="card-rul">
              <span className="num">{e.predicted_rul}</span>
              <span className="unit">cycles left</span>
            </div>

            <div className="bar">
              <div
                className="bar-range"
                style={{
                  left: `${lowPct}%`,
                  width: `${Math.max(0, highPct - lowPct)}%`,
                  background: meta.color,
                }}
              />
              <div
                className="bar-fill"
                style={{ width: `${pct}%`, background: meta.color }}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}
