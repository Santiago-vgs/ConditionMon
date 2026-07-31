import { MAINTENANCE_THRESHOLD, STATUS, WARNING_THRESHOLD } from "../config";

// The landing view: three counts, one per status band. Showing all 100 engines
// at once made the urgent handful indistinguishable from the healthy majority,
// so the fleet is collapsed to its three numbers and the engine list only
// appears once someone picks a band.
//
// Ordered most urgent first — the number a maintenance planner opens this for is
// the leftmost one.
const TABS = [
  {
    key: "MAINTENANCE_REQUIRED",
    detail: `Under ${MAINTENANCE_THRESHOLD} cycles left`,
  },
  {
    key: "WARNING",
    detail: `${MAINTENANCE_THRESHOLD}–${WARNING_THRESHOLD} cycles left`,
  },
  {
    key: "OK",
    detail: `Over ${WARNING_THRESHOLD} cycles left`,
  },
];

export default function CategoryTabs({ counts, active, onSelect }) {
  return (
    <div className="tabs">
      {TABS.map(({ key, detail }) => {
        const meta = STATUS[key];
        const isActive = active === key;
        const count = counts[key] ?? 0;
        return (
          // Disclosure rather than role="tab": a tablist implies arrow-key
          // navigation and exactly one selected tab, and here every category can
          // be closed at once — that collapsed state is the whole point.
          <button
            key={key}
            id={`tab-${key}`}
            aria-expanded={isActive}
            aria-controls="engine-panel"
            className={`tab${isActive ? " active" : ""}`}
            style={isActive ? { boxShadow: `0 0 0 2px ${meta.color}, var(--shadow)` } : undefined}
            onClick={() => onSelect(isActive ? null : key)}
          >
            <span className="tab-count" style={{ color: meta.color }}>
              {count}
            </span>
            <span className="tab-label">{meta.label}</span>
            <span className="tab-detail">{detail}</span>
            <span className="tab-cue">
              {isActive ? "Hide engines" : `Show ${count === 1 ? "engine" : "engines"}`}
            </span>
          </button>
        );
      })}
    </div>
  );
}
