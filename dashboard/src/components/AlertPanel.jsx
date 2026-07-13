import { STATUS } from "../config";

// A single white card listing engines that need attention, most urgent first.
export default function AlertPanel({ engines, onSelect }) {
  const alerts = engines
    .filter((e) => e.status !== "OK")
    .sort((a, b) => a.predicted_rul - b.predicted_rul);

  return (
    <aside className="alerts">
      <h2 className="section">Needs attention</h2>
      <div className="alerts-card">
        {alerts.length === 0 ? (
          <p className="empty">All engines healthy.</p>
        ) : (
          <ul>
            {alerts.map((e) => {
              const meta = STATUS[e.status] ?? STATUS.OK;
              return (
                <li key={e.engine_id} onClick={() => onSelect(e)}>
                  <span className="dot" style={{ background: meta.color }} />
                  <span className="row-name">Engine {e.engine_id}</span>
                  <span className="row-rul">
                    {e.predicted_rul}
                    <span className="row-unit"> cyc</span>
                  </span>
                  <span className="chev">›</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
