import { STATUS } from "../config";

// Engines that need attention (not OK), sorted by urgency (lowest RUL first).
export default function AlertPanel({ engines, onSelect }) {
  const alerts = engines
    .filter((e) => e.status !== "OK")
    .sort((a, b) => a.predicted_rul - b.predicted_rul);

  return (
    <aside className="alert-panel">
      <h2>
        Alerts <span className="count">{alerts.length}</span>
      </h2>
      {alerts.length === 0 ? (
        <p className="empty">All engines healthy.</p>
      ) : (
        <ul>
          {alerts.map((e) => {
            const meta = STATUS[e.status] ?? STATUS.OK;
            return (
              <li key={e.engine_id} onClick={() => onSelect(e)}>
                <span className="status-dot" style={{ background: meta.color }} />
                <span className="alert-engine">Engine {e.engine_id}</span>
                <span className="alert-rul" style={{ color: meta.color }}>
                  {e.predicted_rul} cyc
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
