# Build Instructions — Turbofan Predictive Maintenance Pipeline

Step-by-step guide to build and deploy this project over ~3 weekends. Each phase ends with something working — don't move on until the checkpoint passes.

> **Rule for working with Claude:** have it explain every transform before you accept the code. You will be asked "walk me through your pipeline" in interviews — the project only pays off if you can answer without notes.

---

## Phase 1 — Local pipeline + model (Weekend 1)

### 1.1 Project setup

```
turbofan-predictive-maintenance/
├── data/
│   ├── raw/            # NASA files go here (gitignored)
│   ├── processed/      # Parquet output (gitignored)
│   └── predictions/    # predictions.json (gitignored)
├── src/
│   ├── etl.py
│   ├── train.py
│   └── features.py
├── dashboard/          # React app (Phase 3)
├── notebooks/          # exploration only — nothing production lives here
├── requirements.txt
├── README.md
└── INSTRUCTIONS.md
```

```bash
python -m venv venv && source venv/bin/activate
pip install pandas numpy scikit-learn xgboost pyarrow matplotlib
pip freeze > requirements.txt
```

### 1.2 Get the data

Download the C-MAPSS dataset (NASA Prognostics Data Repository — search "CMAPSS turbofan"). Start with **FD001 only** (single operating condition, single fault mode — the simplest subset). You need:

- `train_FD001.txt` — engines run to failure (training data)
- `test_FD001.txt` — engines cut off before failure
- `RUL_FD001.txt` — true RUL at cutoff for each test engine

Columns (space-separated, no header): `unit_id, cycle, setting_1..3, sensor_1..21`.

### 1.3 Explore first (1–2 hours, notebook)

Before writing the ETL, look at the data so the transforms make sense:

- Plot 3–4 sensors over time for a handful of engines — you should *see* degradation trends in some (e.g. sensors 2, 3, 4, 7, 11, 12, 15) and flat lines in others (e.g. sensors 1, 5, 10, 16, 18, 19).
- Confirm engines have different lifetimes (the failure cycle varies per engine).
- This is where your "which sensors did you drop and why?" interview answer comes from.

### 1.4 Build `etl.py`

Steps, in order:

1. **Load** raw txt → DataFrame with proper column names.
2. **Compute RUL label** (train set): `rul = df.groupby('unit_id')['cycle'].transform('max') - df['cycle']`. Clip at 125: `df['rul'] = df['rul'].clip(upper=125)`.
3. **Drop dead sensors** — drop any sensor whose standard deviation ≈ 0 across the dataset. Do it programmatically (threshold), not by hardcoding, and log what was dropped.
4. **Normalise** remaining sensors with min-max scaling. Fit the scaler on train only, apply to test. Save the scaler (`joblib`) — you need identical scaling at inference.
5. **Rolling features** — per engine, add rolling mean and rolling std over a 5-cycle window for each kept sensor. Use `groupby('unit_id').rolling(5)`; back-fill the first few cycles.
6. **Write Parquet** to `data/processed/`.

**Checkpoint:** `python src/etl.py` produces `train.parquet` / `test.parquet`; row counts match raw; RUL for each engine's final training row = 0.

### 1.5 Build `train.py`

1. Load processed train data.
2. **Split by engine ID, not by row** — e.g. engines 1–80 train, 81–100 validation. Random row splits leak adjacent cycles from the same engine into both sets and inflate your score. (This is a classic interview probe — know it.)
3. Train **two** models so you can compare: `RandomForestRegressor` and `XGBRegressor` with default-ish params.
4. Evaluate with **RMSE** on the validation engines. A reasonable FD001 target is RMSE in the high teens to low 20s. Don't chase leaderboard numbers — the project is the pipeline, not the score.
5. Print/save **feature importances** — another ready-made interview answer ("rolling means of sensors 11 and 4 dominated").
6. Score the test set at each engine's final cycle and write `data/predictions/predictions.json`:

```json
[
  {"engine_id": 1, "current_cycle": 31, "predicted_rul": 112, "status": "OK"},
  {"engine_id": 2, "current_cycle": 49, "predicted_rul": 24, "status": "MAINTENANCE_REQUIRED"}
]
```

Status rule: `MAINTENANCE_REQUIRED` if predicted RUL < 30, `WARNING` if < 60, else `OK`.

**Checkpoint:** model trains in under a minute, RMSE is sane, predictions.json validates.

---

## Phase 2 — Lift onto AWS (Weekend 2)

### 2.1 S3 buckets

Create one bucket (e.g. `svargas-turbofan-pm`) with three prefixes:

```
raw/          ← upload the three NASA txt files once
processed/
predictions/
```

Keep the bucket private. Use the medallion vocabulary in your README — raw=bronze, processed=silver, predictions=gold.

### 2.2 Point the pipeline at S3

- Add `boto3` + an `--s3` flag (or env var) so `etl.py` and `train.py` read/write S3 paths instead of local ones. `pandas.read_parquet`/`to_parquet` handle `s3://` URIs directly with `s3fs` installed.
- Set up an IAM user with least-privilege access to that one bucket; configure credentials via `aws configure`. **Never commit keys.** Add `.env` and `data/` to `.gitignore` on day one.

**Checkpoint:** full run end-to-end against S3 — raw in S3 → processed Parquet in S3 → predictions.json in S3 — from a clean clone.

### 2.3 Optional but high-value: Lambda trigger

Package `etl.py` as a Lambda triggered by an S3 `ObjectCreated` event on `raw/`. Upload a raw file → processed Parquet appears automatically. This is the single most impressive line in the README ("event-driven ETL"). If Lambda packaging fights you (pandas layers can be fiddly), it's fine to ship with a manually-run job and list Lambda as the next step — a working simple thing beats a broken fancy thing.

### 2.4 Expose predictions to the frontend

Simplest first:
1. **Presigned URL** or public-read on the single `predictions/predictions.json` object (nothing else public).
2. **Stretch:** API Gateway + a tiny Lambda that reads the JSON from S3 and returns it — lets you say "I built a REST API" and add CORS properly.

---

## Phase 3 — Dashboard + polish (Weekend 3)

### 3.1 Dashboard (React)

Three components, nothing more:

1. **Fleet grid** — one card per engine, coloured by status (green/amber/red), showing predicted RUL.
2. **Engine detail** — click an engine → recent sensor trends or RUL history chart.
3. **Alert panel** — engines below threshold, sorted by urgency.

Fetch `predictions.json` on load. Deploy free on Vercel (you already know that workflow from The Clean Tones site).

### 3.2 README + demo

- Architecture diagram (the ASCII one in README.md, or draw it in draw.io and export PNG).
- **Write the README in your own words** — recruiters and interviewers can smell generated boilerplate, and writing it is how you cement understanding.
- Record a 2–3 minute screen capture: upload a raw file → show processed output appear → open dashboard → point at a flagged engine. Link it at the top of the README.
- Pin the repo on your GitHub profile and link it from santiagovargas.dev.

### 3.3 Pre-interview self-test

Close all notes and answer out loud:

1. What is RUL and how is the label computed?
2. Why did you drop some sensors? Which ones?
3. Why split train/validation by engine ID?
4. Why Parquet? Why batch instead of streaming?
5. Walk me through what happens from raw file landing in S3 to a red card on the dashboard.
6. What would you do differently at production scale? (e.g. orchestration with Airflow/Step Functions, data quality checks, model retraining cadence, monitoring)

If you can answer all six smoothly, the project is interview-ready.

---

## Timeline summary

| Phase | Time | Deliverable |
|-------|------|-------------|
| 1 | Weekend 1 | Local ETL + model + predictions.json |
| 2 | Weekend 2 | Same pipeline running on S3 (+ Lambda stretch) |
| 3 | Weekend 3 | Deployed dashboard, README, demo video |
