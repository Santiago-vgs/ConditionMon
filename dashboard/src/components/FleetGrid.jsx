import { STATUS } from "../config";

// One card per engine, coloured by status, showing predicted RUL.
// Clicking a card opens the detail view (handled by the parent).
export default function FleetGrid({ engines, onSelect, selectedId }) {
  return (
    <div className="fleet-grid">
      {engines.map((e) => {
        const meta = STATUS[e.status] ?? STATUS.OK;
        const selected = e.engine_id === selectedId;
        return (
          <button
            key={e.engine_id}
            className={`engine-card${selected ? " selected" : ""}`}
            style={{ borderColor: meta.color }}
            onClick={() => onSelect(e)}
          >
            <span className="status-dot" style={{ background: meta.color }} />
            <div className="engine-id">Engine {e.engine_id}</div>
            <div className="engine-rul">
              {e.predicted_rul}
              <span className="unit"> cyc</span>
            </div>
            <div className="engine-status" style={{ color: meta.color }}>
              {meta.label}
            </div>
          </button>
        );
      })}
    </div>
  );
}
