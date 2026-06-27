"""Feature engineering shared between training and inference.

Kept separate from etl.py because the *exact same* transforms must run at
inference time. If train and serve compute features differently, your live
predictions silently drift from what the model learned — a classic prod bug.
"""

from __future__ import annotations

import pandas as pd

ID_COL = "unit_id"
CYCLE_COL = "cycle"
ROLL_WINDOW = 5


def add_rolling_features(
    df: pd.DataFrame,
    sensor_cols: list[str],
    window: int = ROLL_WINDOW,
) -> pd.DataFrame:
    """Add per-engine rolling mean & std for each sensor.

    Why rolling: a single cycle's reading is noisy. A short trailing window
    smooths it and, via the std, captures how *volatile* the sensor is becoming
    near failure — both are stronger signals than the raw value alone.

    Why per engine (groupby unit_id): a rolling window must never reach across
    an engine boundary into a different engine's history.

    The first `window-1` cycles of each engine have an incomplete window, so the
    rolling op yields NaN there; we back-fill them with the first valid value so
    no rows are dropped.
    """
    out = df.copy()
    grouped = out.groupby(ID_COL)[sensor_cols]

    roll_mean = grouped.rolling(window, min_periods=1).mean()
    roll_std = grouped.rolling(window, min_periods=1).std()

    # groupby().rolling() returns a (unit_id, original_index) MultiIndex;
    # drop the group level so it realigns with `out`'s row index.
    roll_mean = roll_mean.reset_index(level=0, drop=True)
    roll_std = roll_std.reset_index(level=0, drop=True)

    for s in sensor_cols:
        out[f"{s}_roll_mean"] = roll_mean[s]
        out[f"{s}_roll_std"] = roll_std[s]

    # std of a 1-element window is NaN -> back-fill within each engine.
    std_cols = [f"{s}_roll_std" for s in sensor_cols]
    out[std_cols] = out.groupby(ID_COL)[std_cols].bfill()
    out[std_cols] = out[std_cols].fillna(0.0)  # engine with a single row

    return out


def feature_columns(sensor_cols: list[str]) -> list[str]:
    """The full model input column list: raw kept sensors + their rolling stats."""
    cols: list[str] = []
    for s in sensor_cols:
        cols += [s, f"{s}_roll_mean", f"{s}_roll_std"]
    return cols
