import { STATUS, RUL_MAX } from "../config";

// Detail sheet for a selected engine. The API exposes the prediction at the
// engine's latest cycle (not full sensor history), so we show RUL as an
// Activity-ring-style gauge (fraction of the 125-cycle cap) — an honest view of
// the data we have. Per-cycle trends would need a second endpoint.
export default function EngineDetail({ engine, onClose }) {
  if (!engine) return null;
  const meta = STATUS[engine.status] ?? STATUS.OK;

  const frac = Math.min(1, engine.predicted_rul / RUL_MAX);
  const R = 52;
  const C = 2 * Math.PI * R;
  const hasRange = engine.rul_low != null && engine.rul_high != null;

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(ev) => ev.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>

        <div className="sheet-head">
          <h2>Engine {engine.engine_id}</h2>
          <span className="pill" style={{ color: meta.color, background: meta.tint }}>
            {meta.label}
          </span>
        </div>

        <div className="ring-wrap">
          <svg className="ring" viewBox="0 0 120 120" width="148" height="148">
            <circle cx="60" cy="60" r={R} className="ring-track" />
            <circle
              cx="60"
              cy="60"
              r={R}
              className="ring-fill"
              stroke={meta.color}
              strokeDasharray={C}
              strokeDashoffset={C * (1 - frac)}
            />
          </svg>
          <div className="ring-center">
            <div className="ring-num">{engine.predicted_rul}</div>
            <div className="ring-unit">cycles left</div>
          </div>
        </div>

        <dl className="sheet-stats">
          <div>
            <dt>Current cycle</dt>
            <dd>{engine.current_cycle}</dd>
          </div>
          {hasRange && (
            <div>
              <dt>Likely range</dt>
              <dd>
                {engine.rul_low}–{engine.rul_high}
              </dd>
            </div>
          )}
          <div>
            <dt>Service in</dt>
            <dd>{Math.max(0, engine.predicted_rul - 30)} cyc</dd>
          </div>
        </dl>

        <p className="thresholds">
          {hasRange && "Range covers the true value 90% of the time. "}
          Maintenance under 30 cycles · Warning under 60
        </p>
      </div>
    </div>
  );
}
