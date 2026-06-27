import { STATUS, RUL_MAX } from "../config";

// Detail view for a clicked engine. The API exposes the prediction at the
// engine's latest cycle (not full sensor history), so we visualise the RUL on a
// 0..125 gauge with the warning/maintenance bands marked — an honest view of the
// data we actually have. (Per-cycle sensor trends would need a second endpoint.)
export default function EngineDetail({ engine, onClose }) {
  if (!engine) return null;
  const meta = STATUS[engine.status] ?? STATUS.OK;
  const pct = Math.min(100, (engine.predicted_rul / RUL_MAX) * 100);

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-card" onClick={(ev) => ev.stopPropagation()}>
        <button className="close" onClick={onClose}>
          ×
        </button>
        <h2>Engine {engine.engine_id}</h2>
        <div className="detail-status" style={{ color: meta.color }}>
          {meta.label}
        </div>

        <dl className="detail-stats">
          <div>
            <dt>Predicted RUL</dt>
            <dd>{engine.predicted_rul} cycles</dd>
          </div>
          <div>
            <dt>Current cycle</dt>
            <dd>{engine.current_cycle}</dd>
          </div>
        </dl>

        {/* RUL gauge with threshold bands at 30 (maintenance) and 60 (warning) */}
        <div className="gauge">
          <div className="gauge-track">
            <div
              className="gauge-fill"
              style={{ width: `${pct}%`, background: meta.color }}
            />
            <span className="gauge-mark" style={{ left: `${(30 / RUL_MAX) * 100}%` }} />
            <span className="gauge-mark" style={{ left: `${(60 / RUL_MAX) * 100}%` }} />
          </div>
          <div className="gauge-labels">
            <span>0</span>
            <span>30</span>
            <span>60</span>
            <span>{RUL_MAX}+</span>
          </div>
        </div>
      </div>
    </div>
  );
}
