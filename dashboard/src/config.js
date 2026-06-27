// Where the dashboard gets its data. Defaults to the deployed API Gateway
// endpoint; override at build time with VITE_API_URL (e.g. on Vercel) or point
// it at a local predictions.json during development.
export const API_URL =
  import.meta.env.VITE_API_URL ||
  "https://wm0mkptokc.execute-api.us-east-1.amazonaws.com/predictions";

// Status thresholds — must match train.py (RUL < 30 = maintenance, < 60 = warning).
export const STATUS = {
  MAINTENANCE_REQUIRED: { label: "Maintenance", color: "#C44E52", order: 0 },
  WARNING: { label: "Warning", color: "#DD8452", order: 1 },
  OK: { label: "OK", color: "#55A868", order: 2 },
};

// RUL is trained with a piecewise-linear cap at 125, so that's our gauge max.
export const RUL_MAX = 125;
