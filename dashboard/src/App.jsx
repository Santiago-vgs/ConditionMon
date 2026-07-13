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

  useEffect(() => {
    fetchPredictions()
      .then((data) => {
        setEngines(data);
        // deep link: #engine-34 opens that engine's sheet directly
        const m = window.location.hash.match(/^#engine-(\d+)$/);
        if (m) {
          const hit = data.find((e) => e.engine_id === Number(m[1]));
          if (hit) setSelected(hit);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const select = (engine) => {
    setSelected(engine);
    const url = engine
      ? `#engine-${engine.engine_id}`
      : window.location.pathname + window.location.search;
    window.history.replaceState(null, "", url);
  };

  const sorted = useMemo(
    () =>
      [...engines].sort(
        (a, b) =>
          (STATUS[a.status]?.order ?? 9) - (STATUS[b.status]?.order ?? 9) ||
          a.predicted_rul - b.predicted_rul
      ),
    [engines]
  );

  const counts = useMemo(() => {
    const c = { MAINTENANCE_REQUIRED: 0, WARNING: 0, OK: 0 };
    engines.forEach((e) => (c[e.status] = (c[e.status] ?? 0) + 1));
    return c;
  }, [engines]);

  return (
    <div className="app">
      <header className="head">
        <h1>Fleet</h1>
        <p className="sub">Turbofan engines · predicted remaining useful life</p>
      </header>

      {!loading && !error && (
        <div className="summary">
          <Stat label="Engines" value={engines.length} color="var(--text)" />
          <Stat label="Maintenance" value={counts.MAINTENANCE_REQUIRED} color="var(--red)" />
          <Stat label="Warning" value={counts.WARNING} color="var(--orange)" />
          <Stat label="Healthy" value={counts.OK} color="var(--green)" />
        </div>
      )}

      {loading && <p className="msg">Loading fleet…</p>}
      {error && <p className="msg error">Couldn’t load data — {error}</p>}

      {!loading && !error && (
        <div className="layout">
          <main>
            <h2 className="section">All engines</h2>
            <FleetGrid
              engines={sorted}
              onSelect={select}
              selectedId={selected?.engine_id}
            />
          </main>
          <AlertPanel engines={engines} onSelect={select} />
        </div>
      )}

      <EngineDetail engine={selected} onClose={() => select(null)} />
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
