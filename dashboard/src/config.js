// Where the dashboard gets its data. Defaults to the deployed API Gateway
// endpoint; override at build time with VITE_API_URL (e.g. on Vercel) or point
// it at a local predictions.json during development.
export const API_URL =
  import.meta.env.VITE_API_URL ||
  "https://wm0mkptokc.execute-api.us-east-1.amazonaws.com/predictions";

// Status thresholds — must match train.py (RUL < 30 = maintenance, < 60 = warning).
// Colours are Apple's system palette (systemRed / systemOrange / systemGreen).
export const STATUS = {
  MAINTENANCE_REQUIRED: { label: "Maintenance", color: "#FF3B30", tint: "#FFEBEA", order: 0 },
  WARNING: { label: "Warning", color: "#FF9500", tint: "#FFF3E0", order: 1 },
  OK: { label: "Healthy", color: "#34C759", tint: "#E6F8EC", order: 2 },
};

// RUL is trained with a piecewise-linear cap at 125, so that's our gauge max.
export const RUL_MAX = 125;
