import { useEffect, useMemo, useState } from "react";
import { fetchPredictions } from "./api";
import { STATUS } from "./config";
import FleetGrid from "./components/FleetGrid";
import AlertPanel from "./components/AlertPanel";
import EngineDetail from "./components/EngineDetail";
import "./App.css";

export default function App() {
  const [engines, setEngines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  // Fetch the fleet once on load.
  useEffect(() => {
    fetchPredictions()
      .then(setEngines)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Sort engines by urgency so the worst show first.
  const sorted = useMemo(
    () =>
      [...engines].sort(
        (a, b) =>
          (STATUS[a.status]?.order ?? 9) - (STATUS[b.status]?.order ?? 9) ||
          a.predicted_rul - b.predicted_rul
      ),
    [engines]
  );

  // Summary counts for the header stat cards.
  const counts = useMemo(() => {
    const c = { MAINTENANCE_REQUIRED: 0, WARNING: 0, OK: 0 };
    engines.forEach((e) => (c[e.status] = (c[e.status] ?? 0) + 1));
    return c;
  }, [engines]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>ConditionMon</h1>
          <p className="subtitle">Turbofan fleet — predicted remaining useful life</p>
        </div>
        <div className="summary">
          <Stat label="Engines" value={engines.length} color="#cbd5e1" />
          <Stat label="Maintenance" value={counts.MAINTENANCE_REQUIRED} color={STATUS.MAINTENANCE_REQUIRED.color} />
          <Stat label="Warning" value={counts.WARNING} color={STATUS.WARNING.color} />
          <Stat label="OK" value={counts.OK} color={STATUS.OK.color} />
        </div>
      </header>

      {loading && <p className="msg">Loading fleet…</p>}
      {error && <p className="msg error">Couldn’t load data: {error}</p>}

      {!loading && !error && (
        <div className="layout">
          <main>
            <FleetGrid
              engines={sorted}
              onSelect={setSelected}
              selectedId={selected?.engine_id}
            />
          </main>
          <AlertPanel engines={engines} onSelect={setSelected} />
        </div>
      )}

      <EngineDetail engine={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="stat">
      <div className="stat-value" style={{ color }}>
        {value}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
