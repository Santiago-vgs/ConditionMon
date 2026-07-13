"""Train RUL regressors on processed FD001 data and emit predictions.

Steps (instructions 1.5):
    1. load processed train.parquet
    2. split by ENGINE ID (not row) -> no leakage between train/val
    3. train RandomForest + XGBoost, compare
    4. evaluate RMSE on held-out engines
    5. dump feature importances
    6. score test set at each engine's final cycle -> predictions.json

Run:
    python src/train.py          # local data/processed -> data/predictions
    python src/train.py --s3     # s3://<bucket>/processed -> s3://<bucket>/predictions
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from xgboost import XGBRegressor

from conformal import apply_conformal, fit_conformal
from features import feature_columns
from storage import PREDICTIONS, PROCESSED, Storage, from_args

ID_COL = "unit_id"
CYCLE_COL = "cycle"
TARGET = "RUL"
VAL_FROM_ENGINE = 81  # engines 1-80 train, 81-100 validation

# status thresholds (instructions 1.5)
MAINTENANCE_BELOW = 30
WARNING_BELOW = 60


def rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def status_for(rul: float) -> str:
    if rul < MAINTENANCE_BELOW:
        return "MAINTENANCE_REQUIRED"
    if rul < WARNING_BELOW:
        return "WARNING"
    return "OK"


def engine_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by engine id. A random *row* split would put cycle N and N+1 of the
    same engine in both train and val — near-identical rows -> leakage that
    inflates the validation score. Splitting whole engines keeps val honest."""
    train = df[df[ID_COL] < VAL_FROM_ENGINE]
    val = df[df[ID_COL] >= VAL_FROM_ENGINE]
    print(f"  train engines: {train[ID_COL].nunique()}, val engines: {val[ID_COL].nunique()}")
    return train, val


def train_models(X_tr, y_tr) -> dict:
    models = {
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=12, n_jobs=-1, random_state=42
        ),
        "xgboost": XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
        ),
    }
    for name, m in models.items():
        m.fit(X_tr, y_tr)
        print(f"  trained {name}")
    return models


def report_importances(model, feats: list[str], top: int = 10) -> None:
    imp = pd.Series(model.feature_importances_, index=feats).sort_values(ascending=False)
    print(f"  top {top} features:")
    for name, val in imp.head(top).items():
        print(f"    {name:>22}: {val:.3f}")


def score_test(store: Storage, model, feats: list[str], bands: list[dict]) -> list[dict]:
    """Predict RUL at each test engine's FINAL observed cycle (the 'now').

    Alongside the point estimate we ship a 90% conformal interval so the
    consumer sees how certain the model is, not just its best guess.
    """
    test = store.read_parquet(f"{PROCESSED}/test.parquet")
    last = test.sort_values(CYCLE_COL).groupby(ID_COL).tail(1).sort_values(ID_COL)
    preds = model.predict(last[feats])
    los, his = apply_conformal(bands, preds)
    out = []
    for (_, row), pred, lo, hi in zip(last.iterrows(), preds, los, his):
        rul = int(round(float(pred)))
        out.append({
            "engine_id": int(row[ID_COL]),
            "current_cycle": int(row[CYCLE_COL]),
            "predicted_rul": rul,
            "rul_low": int(round(float(lo))),
            "rul_high": int(round(float(hi))),
            "status": status_for(rul),
        })
    return out


def run(store: Storage) -> None:
    print(f"Storage: {store}")
    df = store.read_parquet(f"{PROCESSED}/train.parquet")
    kept_sensors = store.load(f"{PROCESSED}/kept_sensors.joblib")
    feats = feature_columns(kept_sensors)

    print("2. Split by engine id:")
    tr, val = engine_split(df)
    X_tr, y_tr = tr[feats], tr[TARGET]
    X_val, y_val = val[feats], val[TARGET]

    print("3. Train models:")
    models = train_models(X_tr, y_tr)

    print("4. Validation RMSE (held-out engines):")
    scores = {name: rmse(y_val, m.predict(X_val)) for name, m in models.items()}
    for name, s in scores.items():
        print(f"    {name:>14}: RMSE {s:.2f}")
    best_name = min(scores, key=scores.get)
    best = models[best_name]
    print(f"  best: {best_name}")

    print("5. Feature importances (best model):")
    report_importances(best, feats)

    print("6. Conformal calibration on held-out engines (90% intervals):")
    bands = fit_conformal(y_val, best.predict(X_val), alpha=0.10)
    for b in bands:
        hi = "inf" if b["hi"] == float("inf") else f"{b['hi']:.0f}"
        print(f"    pred in [{b['lo']:.0f}, {hi}): "
              f"[{b['adj_lo']:+.1f}, {b['adj_hi']:+.1f}]  (n={b['n']})")

    print("7. Score test set -> predictions.json:")
    predictions = score_test(store, best, feats, bands)
    store.write_json(predictions, f"{PREDICTIONS}/predictions.json")
    store.dump(best, f"{PROCESSED}/model.joblib")
    store.dump(bands, f"{PROCESSED}/conformal.joblib")

    n_maint = sum(p["status"] == "MAINTENANCE_REQUIRED" for p in predictions)
    n_warn = sum(p["status"] == "WARNING" for p in predictions)
    print(f"   wrote {len(predictions)} predictions "
          f"({n_maint} MAINTENANCE, {n_warn} WARNING, rest OK)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3", action="store_true", help="read/write S3 instead of local")
    parser.add_argument("--bucket", help="override S3 bucket name")
    args = parser.parse_args()
    run(from_args(args.s3, args.bucket))


if __name__ == "__main__":
    main()
