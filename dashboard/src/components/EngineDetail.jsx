import { useEffect, useState } from "react";
import { fetchHistory } from "../api";
import { STATUS } from "../config";
import DegradationChart from "./DegradationChart";

// Detail sheet for a selected engine. The headline number comes from the fleet
// snapshot that's already in memory; the degradation history is a second,
// per-engine request fired when the sheet opens, so the fleet view stays cheap
// and only the engines someone actually looks at cost a fetch.
export default function EngineDetail({ engine, onClose }) {
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState(null);
  const engineId = engine?.engine_id;

  useEffect(() => {
    if (engineId == null) return;
    let cancelled = false; // clicking through engines fast must not paint stale data
    setHistory(null);
    setHistoryError(null);
    fetchHistory(engineId)
      .then((data) => !cancelled && setHistory(data))
      .catch((err) => !cancelled && setHistoryError(err.message));
    return () => {
      cancelled = true;
    };
  }, [engineId]);

  if (!engine) return null;
  const meta = STATUS[engine.status] ?? STATUS.OK;
  const hasRange = engine.rul_low != null && engine.rul_high != null;

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet sheet-wide" onClick={(ev) => ev.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>

        <div className="sheet-head">
          <h2>Engine {engine.engine_id}</h2>
          <span className="pill" style={{ color: meta.color, background: meta.tint }}>
            {meta.label}
          </span>
        </div>

        <div className="sheet-headline">
          <span className="sheet-headline-num" style={{ color: meta.color }}>
            {engine.predicted_rul}
          </span>
          <span className="sheet-headline-unit">cycles left</span>
        </div>

        {history ? (
          <DegradationChart
            points={history.points}
            label={`engine ${engine.engine_id}`}
          />
        ) : (
          <div className={`chart-placeholder${historyError ? " error" : ""}`}>
            {historyError
              ? `Couldn’t load history — ${historyError}`
              : "Loading history…"}
          </div>
        )}

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
