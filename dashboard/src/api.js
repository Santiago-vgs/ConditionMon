import { API_URL, historyUrl, METRICS_URL } from "./config";

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API returned ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Fetch the fleet predictions from the API. Returns the parsed array
// [{ engine_id, current_cycle, predicted_rul, rul_low, rul_high, status }, ...]
// where [rul_low, rul_high] is a 90% conformal prediction interval.
export async function fetchPredictions() {
  return getJson(API_URL);
}

// Fetch one engine's per-cycle degradation history:
// { engine_id, current_cycle, predicted_rul, status, points: [
//     { cycle, predicted_rul, rul_low, rul_high, actual_rul }, ... ] }
// Responses are cached for the session — a history only changes when the
// pipeline reruns, and reopening the same engine is the common case.
const cache = new Map();

// Model-health metrics written by insights.py: interval coverage, error by RUL
// band, the alert-threshold cost sweep, backtest results and PSI drift.
export async function fetchMetrics() {
  return getJson(METRICS_URL);
}

export async function fetchHistory(engineId) {
  if (!cache.has(engineId)) {
    // store the promise, not the result, so concurrent opens share one request
    cache.set(
      engineId,
      getJson(historyUrl(engineId)).catch((err) => {
        cache.delete(engineId); // don't cache a failure — let a retry through
        throw err;
      })
    );
  }
  return cache.get(engineId);
}
