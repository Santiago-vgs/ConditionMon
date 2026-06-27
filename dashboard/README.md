# ConditionMon Dashboard

React + Vite frontend for the [ConditionMon](../README.md) turbofan predictive-
maintenance project. Fetches the fleet's `predictions.json` from the API and shows:

- **Fleet grid** — one card per engine, coloured by status (OK / Warning / Maintenance).
- **Engine detail** — click an engine for its predicted RUL and current cycle.
- **Alert panel** — engines below threshold, sorted by urgency.

## Develop

```bash
npm install
npm run dev
```

## Configuration

The data source is set in `src/config.js` and can be overridden at build time:

```bash
VITE_API_URL=https://your-api-gateway-url/predictions npm run build
```

By default it points at the deployed API Gateway endpoint. For offline work, point
`VITE_API_URL` at a local `predictions.json`.

## Deploy

Static build (`npm run build` → `dist/`); deploys cleanly on Vercel. Set
`VITE_API_URL` as a Vercel environment variable.
