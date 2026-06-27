import { API_URL } from "./config";

// Fetch the fleet predictions from the API. Returns the parsed array
// [{ engine_id, current_cycle, predicted_rul, status }, ...].
export async function fetchPredictions() {
  const res = await fetch(API_URL);
  if (!res.ok) {
    throw new Error(`API returned ${res.status} ${res.statusText}`);
  }
  return res.json();
}
