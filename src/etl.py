"""ETL for the C-MAPSS FD001 turbofan dataset.

Pipeline (raw txt -> processed Parquet):
    1. load          raw space-separated txt -> named DataFrame
    2. label RUL     per-engine remaining-useful-life, clipped at 125 (train only)
    3. drop dead     remove sensors with std ~ 0 (no signal), found by threshold
    4. normalise     min-max scale kept sensors; FIT ON TRAIN, apply to test
    5. rolling feats  per-engine rolling mean/std (see features.py)
    6. write          Parquet to processed/

Run:
    python src/etl.py            # local data/raw -> data/processed
    python src/etl.py --s3       # s3://<bucket>/raw -> s3://<bucket>/processed
"""

from __future__ import annotations

import argparse

import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from features import add_rolling_features
from storage import PROCESSED, RAW, Storage, from_args

ID_COL = "unit_id"
CYCLE_COL = "cycle"
SETTING_COLS = [f"setting_{i}" for i in (1, 2, 3)]
ALL_SENSORS = [f"sensor_{i}" for i in range(1, 22)]
COLS = [ID_COL, CYCLE_COL, *SETTING_COLS, *ALL_SENSORS]

RUL_CLIP = 125
DEAD_STD_THRESHOLD = 1e-6


# ---------------------------------------------------------------- 1. load
def load_raw(store: Storage, name: str) -> pd.DataFrame:
    """Read one raw FD001 txt file into a properly-named DataFrame."""
    df = store.read_csv(f"{RAW}/{name}", sep=r"\s+", header=None, names=COLS)
    print(f"  loaded {name}: {df.shape[0]} rows, {df[ID_COL].nunique()} engines")
    return df


# ---------------------------------------------------------------- 2. label
def add_rul(df: pd.DataFrame, clip: int = RUL_CLIP) -> pd.DataFrame:
    """Add the RUL label (train only): cycles remaining until failure.

    In the training set each engine runs to failure, so its max cycle is the
    failure point and RUL = max_cycle - current_cycle. We clip at `clip`: early
    in life degradation is negligible, so a true RUL of 250 is no more 'healthy'
    than 125. Clipping stops the model wasting capacity fitting that flat region
    and is the standard C-MAPSS convention (piecewise-linear RUL).
    """
    df = df.copy()
    df["RUL"] = df.groupby(ID_COL)[CYCLE_COL].transform("max") - df[CYCLE_COL]
    df["RUL"] = df["RUL"].clip(upper=clip)
    return df


# ---------------------------------------------------------------- 3. drop dead
def find_dead_sensors(df: pd.DataFrame, threshold: float = DEAD_STD_THRESHOLD) -> list[str]:
    """Sensors whose std is ~0 across the training set carry no information."""
    stds = df[ALL_SENSORS].std()
    dead = stds[stds < threshold].index.tolist()
    print(f"  dead sensors (std < {threshold}): {dead}")
    return dead


# ---------------------------------------------------------------- 4. normalise
def fit_scaler(train: pd.DataFrame, sensor_cols: list[str]) -> MinMaxScaler:
    """Fit min-max scaler on TRAIN ONLY. Fitting on test would leak test
    distribution into training — and at serve time you won't have test stats."""
    scaler = MinMaxScaler()
    scaler.fit(train[sensor_cols])
    return scaler


def apply_scaler(df: pd.DataFrame, scaler: MinMaxScaler, sensor_cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    df[sensor_cols] = scaler.transform(df[sensor_cols])
    return df


# ---------------------------------------------------------------- orchestration
def run(store: Storage) -> None:
    print(f"Storage: {store}")

    print("1-2. Load + label train:")
    train = add_rul(load_raw(store, "train_FD001.txt"))
    raw_train_rows = train.shape[0]  # capture before any row-changing step
    print("     Load test (no RUL label - test engines haven't failed yet):")
    test = load_raw(store, "test_FD001.txt")

    print("3. Drop dead sensors (threshold on TRAIN):")
    dead = find_dead_sensors(train)
    keep = [s for s in ALL_SENSORS if s not in dead]
    print(f"   keeping {len(keep)} sensors")

    print("4. Normalise (fit on train, apply to both):")
    scaler = fit_scaler(train, keep)
    train = apply_scaler(train, scaler, keep)
    test = apply_scaler(test, scaler, keep)

    print("5. Rolling features (per engine):")
    train = add_rolling_features(train, keep)
    test = add_rolling_features(test, keep)

    print("6. Write Parquet + artifacts:")
    drop_cols = dead + SETTING_COLS  # settings are constant in FD001 too
    train = train.drop(columns=drop_cols)
    test = test.drop(columns=drop_cols)
    store.write_parquet(train, f"{PROCESSED}/train.parquet")
    store.write_parquet(test, f"{PROCESSED}/test.parquet")
    store.dump(scaler, f"{PROCESSED}/scaler.joblib")
    store.dump(keep, f"{PROCESSED}/kept_sensors.joblib")
    print(f"   wrote train.parquet {train.shape}, test.parquet {test.shape}")

    # ---- checkpoint assertions (instructions 1.4) ----
    assert train.shape[0] == raw_train_rows, "train row count changed!"
    final_rul = train.groupby(ID_COL)["RUL"].min()
    assert (final_rul == 0).all(), "some engine's final RUL != 0!"
    print("\nCheckpoint PASSED: row counts match, every engine's final RUL = 0.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3", action="store_true", help="read/write S3 instead of local")
    parser.add_argument("--bucket", help="override S3 bucket name")
    args = parser.parse_args()
    run(from_args(args.s3, args.bucket))


if __name__ == "__main__":
    main()
