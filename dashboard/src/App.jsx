import { useEffect, useMemo, useState } from "react";
import { fetchPredictions } from "./api";
import { STATUS } from "./config";
import CategoryTabs from "./components/CategoryTabs";
import FleetGrid from "./components/FleetGrid";
import EngineDetail from "./components/EngineDetail";
import "./App.css";

export default function App() {
  const [engines, setEngines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  // which status band is expanded; null means the collapsed landing view
  const [activeStatus, setActiveStatus] = useState(null);

  useEffect(() => {
    fetchPredictions()
      .then((data) => {
        setEngines(data);
        // deep link: #engine-34 opens that engine's sheet directly. Expand its
        // band too, so closing the sheet lands on a list containing it rather
        // than on the empty landing view.
        const m = window.location.hash.match(/^#engine-(\d+)$/);
        if (m) {
          const hit = data.find((e) => e.engine_id === Number(m[1]));
          if (hit) {
            setSelected(hit);
            setActiveStatus(hit.status);
          }
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

  const counts = useMemo(() => {
    const c = { MAINTENANCE_REQUIRED: 0, WARNING: 0, OK: 0 };
    engines.forEach((e) => (c[e.status] = (c[e.status] ?? 0) + 1));
    return c;
  }, [engines]);

  // Only the expanded band, most urgent first. Sorting by RUL rather than id
  // means the engine to act on first is the one read first.
  const visible = useMemo(
    () =>
      activeStatus === null
        ? []
        : engines
            .filter((e) => e.status === activeStatus)
            .sort((a, b) => a.predicted_rul - b.predicted_rul),
    [engines, activeStatus]
  );

  const meta = activeStatus ? STATUS[activeStatus] : null;

  return (
    <div className="app">
      <header className="head">
        <h1>Fleet</h1>
        <p className="sub">
          {loading || error
            ? "Turbofan engines · predicted remaining useful life"
            : `${engines.length} turbofan engines · predicted remaining useful life`}
        </p>
      </header>

      {loading && <p className="msg">Loading fleet…</p>}
      {error && <p className="msg error">Couldn’t load data — {error}</p>}

      {!loading && !error && (
        <>
          <CategoryTabs
            counts={counts}
            active={activeStatus}
            onSelect={setActiveStatus}
          />

          <section
            id="engine-panel"
            aria-labelledby={activeStatus ? `tab-${activeStatus}` : undefined}
          >
            {activeStatus === null ? (
              <p className="panel-hint">
                Choose a category above to see the engines in it.
              </p>
            ) : visible.length === 0 ? (
              <p className="panel-hint">
                No engines are currently {meta.label.toLowerCase()}.
              </p>
            ) : (
              <>
                <h2 className="section">
                  {meta.label}
                  <span className="section-count">
                    {visible.length} {visible.length === 1 ? "engine" : "engines"}
                  </span>
                </h2>
                <FleetGrid
                  engines={visible}
                  onSelect={select}
                  selectedId={selected?.engine_id}
                />
              </>
            )}
          </section>
        </>
      )}

      <EngineDetail engine={selected} onClose={() => select(null)} />
    </div>
  );
}
