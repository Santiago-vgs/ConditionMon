# ConditionMon Dashboard

React + Vite frontend for the [ConditionMon](../README.md) turbofan predictive-
maintenance project. Fetches the fleet's `predictions.json` from the API and shows:

- **Categories** — the landing view is three counts, one per status band
  (Maintenance / Warning / Healthy). Showing all 100 engines at once buried the
  urgent handful in the healthy majority, so the list stays collapsed until a
  category is chosen.
- **Engine list** — the chosen category only, most urgent first.
- **Engine detail** — click an engine for its full degradation history: predicted
  RUL per cycle with its 90% conformal band, the true RUL for comparison, and the
  cost-optimal alert threshold τ. Hover any cycle to read the numbers.

## Develop

```bash
npm install
npm run dev
```

That runs against the deployed API. To work offline from a local pipeline run
(`python src/etl.py && python src/train.py && python src/history.py`), a dev-only
middleware in `vite.config.js` serves `data/predictions/` at `/dev-data`:

```bash
VITE_API_URL=/dev-data/predictions.json \
VITE_HISTORY_URL='/dev-data/history/engine_{id}.json' npm run dev
```

## Configuration

The data source is set in `src/config.js` and can be overridden at build time:

```bash
VITE_API_URL=https://your-api-gateway-url/predictions npm run build
```

`VITE_HISTORY_URL` is derived from `VITE_API_URL` (swapping `/predictions` for
`/history`) unless set explicitly. It accepts an `{id}` placeholder for static
hosting; without one it appends `?engine=<id>`, which is what the Lambda expects.

## Deploy

Live at [dashboard-nine-psi-65.vercel.app](https://dashboard-nine-psi-65.vercel.app).

Static build (`npm run build` → `dist/`), deployed on Vercel from this directory:

```bash
cd dashboard && npx vercel --prod
```

The Vercel project's root directory is `dashboard/`, not the repo root — running
the deploy from the repo root uploads the repository as static files without
building. No environment variables are set: `src/config.js` already defaults to
the deployed API Gateway URL. Override `VITE_API_URL` there if the API moves.
