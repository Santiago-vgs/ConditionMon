// Where the dashboard gets its data. Defaults to the deployed API Gateway
// endpoint; override at build time with VITE_API_URL (e.g. on Vercel) or point
// it at a local predictions.json during development.
export const API_URL =
  import.meta.env.VITE_API_URL ||
  "https://wm0mkptokc.execute-api.us-east-1.amazonaws.com/predictions";

// Per-engine degradation history. The deployed API takes ?engine=<id>; the dev
// mount serves one static file per engine instead, so the override accepts an
// `{id}` placeholder and falls back to the query-param form when there isn't one.
const HISTORY_TEMPLATE =
  import.meta.env.VITE_HISTORY_URL || API_URL.replace(/\/predictions$/, "/history");

export function historyUrl(engineId) {
  return HISTORY_TEMPLATE.includes("{id}")
    ? HISTORY_TEMPLATE.replace("{id}", engineId)
    : `${HISTORY_TEMPLATE}?engine=${engineId}`;
}

// Status thresholds — must match train.py (RUL < 30 = maintenance, < 60 = warning).
// Colours are Apple's system palette (systemRed / systemOrange / systemGreen).
export const STATUS = {
  MAINTENANCE_REQUIRED: { label: "Maintenance", color: "#FF3B30", tint: "#FFEBEA", order: 0 },
  WARNING: { label: "Warning", color: "#FF9500", tint: "#FFF3E0", order: 1 },
  OK: { label: "Healthy", color: "#34C759", tint: "#E6F8EC", order: 2 },
};

export const MAINTENANCE_THRESHOLD = 30;
export const WARNING_THRESHOLD = 60;

// Cost-optimal alert threshold from the policy sweep in insights.py — the point
// where expected cost per engine is lowest, given a 10-cycle logistics lead.
export const TAU = 23;

// RUL is trained with a piecewise-linear cap at 125, so that's our gauge max.
export const RUL_MAX = 125;
