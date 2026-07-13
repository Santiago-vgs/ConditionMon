# ConditionMon — Turbofan Predictive Maintenance

I built ConditionMon to answer a question I kept hitting in interviews: can I take
a messy ML idea all the way from raw data to something actually running in the cloud?

It predicts how many flights a jet engine has left before it needs servicing — its
**Remaining Useful Life (RUL)** — and shows the whole fleet on a dashboard, so you
service each engine *just before* it fails. Not too early (you throw away good parts),
not too late (for a jet engine, that's catastrophic).

The whole thing is one reproducible pipeline: NASA sensor data → cleaned features →
a trained model → predictions, fronted by a serverless API and a React dashboard.
The same code runs on my laptop or on AWS behind a single flag. Below is what I built
and, more importantly, *why* I made each call.

> 📺 **Demo:** _add a 2–3 min screen capture link here_
> 🔗 **Live dashboard:** _add Vercel URL here_

---

## How it fits together

```
 raw (bronze)            processed (silver)              predictions (gold)
 ┌───────────────┐       ┌────────────────────┐          ┌────────────────────┐
 │ *_FD001.txt   │       │ train/test.parquet │          │ predictions.json   │
 │ (NASA C-MAPSS)│──────▶│ scaler.joblib      │─────────▶│ model.joblib       │
 │               │ etl.py│ kept_sensors.joblib│ train.py │                    │
 └───────────────┘       └────────────────────┘          └─────────┬──────────┘
        same code runs on local disk OR s3:// (one --s3 flag)      │
                                                                    ▼
                                       API Gateway + Lambda  ──▶  React dashboard
                                       (reads the private S3 object, adds CORS)
```

The three stages follow the **medallion** convention (bronze → silver → gold). I keep
them as folders locally and as prefixes in one private S3 bucket, and a small `Storage`
abstraction (`src/storage.py`) means going to the cloud is a flag, not a rewrite. That
symmetry was deliberate — I wanted local development and the cloud run to share exactly
one code path.

## What it actually does (FD001 results)

| Metric | Value |
|--------|-------|
| Validation RMSE (held-out engines) | **~18.9 cycles** |
| RMSE in the critical band (RUL < 30) | **~11 cycles** — sharpest where it matters |
| Test RMSE | **~17.3 cycles** (≤ validation, so it's not overfitting) |
| 90% conformal interval coverage | **exactly 90/100** on unseen test engines |
| Fleet backtest (cost-optimal policy) | **20/20 failures caught**, median **22 cycles** of warning |
| `MAINTENANCE_REQUIRED` alarm precision | **~94%** (17 of 18 flagged engines truly had < 30 cycles left) |

I trained two models (Random Forest and XGBoost) and compared them. They land within
~0.02 RMSE of each other — which I actually like as a result: it tells me the
**features** are doing the work, not some fancy model. Honest beats impressive.

Every prediction also ships with a **90% prediction interval** (split conformal,
calibrated per RUL band on held-out engines), because "40 cycles left" is not something
you can schedule a shop visit against — "27 to 63, 90% sure" is. The alert threshold
itself isn't a gut call either: I swept it under a cost model (unscheduled failure ≫
scheduled service, plus a minimum-lead-time logistics constraint) and backtested the
policy over every held-out engine's full life. The deeper analysis — including a drift
monitor whose one alarm turned out to be a lesson in interpreting drift, not a bug —
is written up in [`docs/INSIGHTS.md`](docs/INSIGHTS.md).

## Tech I used

- **Pipeline:** Python, pandas, scikit-learn, XGBoost, PyArrow (Parquet)
- **Cloud:** AWS S3, Lambda, API Gateway, IAM (least-privilege), `boto3` / `fsspec` / `s3fs`
- **Frontend:** React + Vite, deployed on Vercel

## Run it yourself

```bash
# 1. environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
brew install libomp          # macOS only: XGBoost needs the OpenMP runtime

# 2. get the data (NASA C-MAPSS, FD001 subset)
python src/download_data.py

# 3. run the pipeline locally
python src/etl.py            # data/raw  → data/processed  (clean + feature-engineer)
python src/train.py          # data/processed → data/predictions/predictions.json
python src/insights.py       # evaluation suite → docs/img/ + docs/insights_metrics.json

# 4. or run the exact same pipeline against S3
python src/etl.py   --s3
python src/train.py --s3

# 5. dashboard
cd dashboard && npm install && npm run dev
```

The cloud setup (S3 bucket, IAM user, API deploy) is a one-time thing — I wrote it up
in [`docs/AWS_SETUP.md`](docs/AWS_SETUP.md), and the API deploys with a single
`python api/deploy.py`.

## Where things live

```
src/            ETL, training, feature engineering, storage abstraction
api/            Lambda handler + one-command deploy/teardown script
dashboard/      React + Vite fleet dashboard
notebooks/      exploration only — nothing production lives here
data/           bronze/silver/gold layers (gitignored — all regenerable)
docs/           deep-dive walkthrough, AWS setup, generated figures
```

## The decisions I'd want to talk through

These are the choices I made on purpose, and the ones I'd expect a good interviewer to
poke at:

- **I compute the label myself: `max(cycle) − cycle` per engine, clipped at 125.**
  Degradation is basically flat early in an engine's life, so an uncapped label just
  asks the model to fit noise. Clipping (piecewise-linear RUL) is the standard fix.
- **I drop dead sensors by a std *threshold*, not a hardcoded list.** Six sensors never
  move in FD001. Finding them by rule means the same code still works on FD002–FD004
  instead of silently being wrong.
- **I fit the scaler on train only, and I split train/validation by engine ID.** Both
  are leakage guards. A random *row* split would scatter adjacent cycles of the same
  engine across both sets — nearly identical rows — and flatter my score dishonestly.
- **Feature logic lives in one shared module** (`features.py`) so training and inference
  compute features identically. Train/serve skew is one of those bugs that only shows up
  in production, and I wanted it impossible by construction.
- **It's batch, not streaming.** Engines get serviced on the ground between flights —
  there's no need for millisecond predictions. Batch is simpler, cheaper, and correct
  for the use case.

If you want the full reasoning with the figures behind it, I wrote a ground-up
walkthrough in [`docs/UNDERSTANDING.md`](docs/UNDERSTANDING.md). The original build plan
I worked from is in [`INSTRUCTIONS.md`](INSTRUCTIONS.md).

## What I'd do next at real scale

Honest about the edges: at production scale I'd add an orchestrator (Airflow or Step
Functions) instead of running scripts by hand, data-quality checks at the bronze layer,
and I'd tighten the API's CORS from `*` to just the dashboard's origin. Drift
*detection* (PSI) is already in `insights.py`; what's missing is the retraining cadence
it should feed. The pipeline is the point here — those are the next layers, not gaps I
overlooked.

## License

MIT — see [`LICENSE`](LICENSE).
