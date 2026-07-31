import { STATUS, RUL_MAX } from "../config";

// One soft white card per engine: name, status pill, the RUL figure, and a thin
// rounded progress bar coloured by status. The lighter band on the bar is the
// 90% prediction interval — how far off the estimate could plausibly be.
//
// Each card ends in an explicit "full analytics" cue. The card is a button and
// opens the degradation chart, but nothing on it said so — the most substantial
// view in the app was reachable only by guessing that a card was clickable.
//
// No status pill: the grid only ever shows one category at a time, so a pill on
// every card would repeat the heading above it. The status colour moves to the
// RUL figure, which is what the eye goes to anyway.
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
            </div>

            <div className="card-rul">
              <span className="num" style={{ color: meta.color }}>
                {e.predicted_rul}
              </span>
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

            <span className="card-cta">
              See full analytics <span aria-hidden="true">›</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
