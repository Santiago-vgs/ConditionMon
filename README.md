# ConditionMon — Turbofan Predictive Maintenance

Predict the **Remaining Useful Life (RUL)** of jet engines from sensor data, and
surface the fleet on a live dashboard so maintenance happens *just before* failure —
not too early (wasted parts), not too late (catastrophic).

End-to-end: a reproducible ML pipeline (NASA C-MAPSS data → cleaned features →
trained model → predictions) that runs identically on a laptop or on AWS, exposed
through a serverless REST API and a React dashboard.

> 📺 **Demo:** _add a 2–3 min screen capture link here_
> 🔗 **Live dashboard:** _add Vercel URL here_

---

## Architecture

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

The three layers follow the **medallion** convention (bronze → silver → gold) and
exist as folders locally or as prefixes in one private S3 bucket. A `Storage`
abstraction (`src/storage.py`) means switching to the cloud is a flag, not a rewrite.

## Results (FD001)

| Metric | Value |
|--------|-------|
| Validation RMSE (held-out engines) | **~18.9 cycles** |
| Test RMSE | **~17.3 cycles** (≤ validation → not overfitting) |
| `MAINTENANCE_REQUIRED` alarm precision | **~94%** (17/18 truly < 30 cycles left) |

Two models (Random Forest, XGBoost) are trained and compared; they land within
~0.02 RMSE, which shows the **features** are doing the work, not model complexity.

## Tech stack

- **Pipeline:** Python, pandas, scikit-learn, XGBoost, PyArrow (Parquet)
- **Cloud:** AWS S3, Lambda, API Gateway, IAM (least-privilege), `boto3` / `fsspec` / `s3fs`
- **Frontend:** React + Vite, deployable on Vercel

## Quickstart

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

# 4. (optional) run the same pipeline against S3
python src/etl.py   --s3
python src/train.py --s3

# 5. dashboard
cd dashboard && npm install && npm run dev
```

Cloud setup (S3 bucket, IAM user, API deploy) is a one-time step — see
[`docs/AWS_SETUP.md`](docs/AWS_SETUP.md). Deploy the API with `python api/deploy.py`.

## Project structure

```
src/            ETL, training, feature engineering, storage abstraction
api/            Lambda handler + one-command deploy/teardown script
dashboard/      React + Vite fleet dashboard
notebooks/      exploration only (nothing production lives here)
data/           bronze/silver/gold layers (gitignored — regenerable)
docs/           deep-dive walkthrough, AWS setup, generated figures
```

## Design decisions

A few of the choices an interviewer (or teammate) tends to ask about:

- **Label by `max(cycle) − cycle` per engine, clipped at 125** — piecewise-linear
  RUL; degradation is flat early in life, so an uncapped label just adds noise.
- **Drop dead sensors by a std *threshold*, not a hardcoded list** — generalises to
  other subsets (FD002–FD004) without editing code.
- **Fit the scaler on train only; split train/validation by engine ID** — two
  guards against data leakage. A random *row* split would put adjacent cycles of the
  same engine in both sets and inflate the score.
- **Feature logic lives in one shared module** (`features.py`) — training and
  inference compute features identically, avoiding train/serve skew.
- **Batch, not streaming** — engines are serviced on the ground; batch is simpler,
  cheaper, and correct for the use case.

The full reasoning, with figures, is in
[`docs/UNDERSTANDING.md`](docs/UNDERSTANDING.md) — a ground-up walkthrough of the
whole project. The original build plan is in [`INSTRUCTIONS.md`](INSTRUCTIONS.md).

## License

_Add a license (MIT is a sensible default for a portfolio project)._
