# ConditionMon — Turbofan Predictive Maintenance

[![CI](https://github.com/Santiago-vgs/ConditionMon/actions/workflows/ci.yml/badge.svg)](https://github.com/Santiago-vgs/ConditionMon/actions/workflows/ci.yml)

The goal of this project is to estimate the Remaining Useful Life (RUL) of turbofan jet engines from sensor data. RUL is the number of operating cycles an engine has left before it needs maintenance. Predicting it lets you schedule servicing late enough to use most of a part's life, but early enough to avoid an in-flight failure.

The repository covers the full path from raw data to a deployed service: an ETL and training pipeline, a serverless inference API, and a React dashboard showing predictions across a fleet. The pipeline runs against local disk or an S3 bucket depending on a single `--s3` flag.

## Dataset

NASA's C-MAPSS turbofan degradation dataset, FD001 subset (High-Pressure Compressor fault, single operating condition). The training set has 100 run-to-failure engines over 20,631 cycles, each with 3 operational settings and 21 sensor readings. The test set gives sensor traces that stop some cycles before failure, with the true RUL provided separately for scoring.

## Pipeline

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
```

Stages follow the bronze/silver/gold layering: raw text, cleaned Parquet, and predictions. Locally these are folders; on AWS they are prefixes in one private S3 bucket. `src/storage.py` selects the backend so both runs use the same code.

## Feature engineering

- **Label.** RUL is computed per engine as `max(cycle) − cycle`, clipped at 125. Early-life degradation is minimal, so an unclipped label trains the model to fit noise; clipping to a piecewise-linear target is standard practice for C-MAPSS.
- **Sensor selection.** Sensors with near-zero variance carry no degradation signal and are dropped by a standard-deviation threshold rather than a fixed list, so the same code generalises to FD002–FD004. Six sensors are constant in FD001.
- **Scaling.** The scaler is fit on the training split only.
- **Splitting.** Train and validation are split by engine ID, not by row, to prevent adjacent cycles of the same engine leaking across the split.
- **Feature parity.** Training and inference import feature logic from one module (`features.py`) so they cannot compute features differently.

## Model and results

Random Forest and XGBoost were trained and compared. Both score within ~0.02 RMSE of each other, indicating the features rather than the model drive performance. Results on FD001:

| Metric | Value |
|--------|-------|
| Validation RMSE (held-out engines) | ~18.9 cycles |
| RMSE, critical band (RUL < 30) | ~11 cycles |
| Test RMSE | ~17.3 cycles |
| 90% conformal interval coverage | 90/100 test engines |
| Fleet backtest, cost-optimal policy | 20/20 failures caught, median 22 cycles' warning |
| `MAINTENANCE_REQUIRED` alarm precision | ~94% (17 of 18 flagged engines under 30 cycles) |

Each prediction carries a 90% interval from split conformal prediction, calibrated per RUL band on held-out engines. The maintenance alert threshold is set from a cost model (unscheduled failure weighted well above scheduled service, with a minimum lead-time constraint) and backtested over each held-out engine's full life. Full evaluation, including a drift monitor and analysis of its one alarm, is in [`docs/INSIGHTS.md`](docs/INSIGHTS.md).

## Stack

- **Pipeline:** Python, pandas, scikit-learn, XGBoost, PyArrow
- **Cloud:** AWS S3, Lambda, API Gateway, IAM, `boto3` / `fsspec` / `s3fs`
- **Frontend:** React + Vite on Vercel

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
brew install libomp          # macOS only: XGBoost's OpenMP runtime

python src/download_data.py  # fetch NASA C-MAPSS FD001

python src/etl.py            # data/raw  → data/processed
python src/train.py          # data/processed → data/predictions/predictions.json
python src/insights.py       # evaluation suite → docs/img/ + docs/insights_metrics.json

python src/etl.py   --s3     # same pipeline against S3
python src/train.py --s3

cd dashboard && npm install && npm run dev
```

AWS setup (bucket, IAM user, API deploy) is documented in [`docs/AWS_SETUP.md`](docs/AWS_SETUP.md). The API deploys with `python api/deploy.py`.

## Repository layout

```
src/            ETL, training, feature engineering, storage abstraction
api/            Lambda handler + deploy/teardown script
dashboard/      React + Vite fleet dashboard
notebooks/      exploration only
data/           bronze/silver/gold layers (gitignored, regenerable)
docs/           walkthrough, AWS setup, generated figures
```

Additional writeups: a ground-up walkthrough in [`docs/UNDERSTANDING.md`](docs/UNDERSTANDING.md) and the original build plan in [`INSTRUCTIONS.md`](INSTRUCTIONS.md).

## Limitations

The pipeline runs as scripts rather than under an orchestrator; at larger scale it would use Airflow or Step Functions, with data-quality checks at the bronze layer. Inference is batch, which suits ground-based servicing between flights. API CORS is currently open (`*`) and would be restricted to the dashboard origin. Drift detection (PSI) exists in `insights.py` but does not yet trigger retraining.

## License

MIT, see [`LICENSE`](LICENSE).
