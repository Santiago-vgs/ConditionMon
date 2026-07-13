"""Tests for rolling-window features (src/features.py).

The key guarantees: no NaNs leak into the model input, and a rolling window
never reaches across an engine boundary (train/serve correctness).
"""

import pandas as pd

from features import add_rolling_features, feature_columns


def _two_engines() -> pd.DataFrame:
    """Engine 1 is constant at 1.0, engine 2 constant at 100.0 — so any cross-
    engine bleed in a rolling stat is immediately visible."""
    rows = []
    for cycle in range(1, 6):
        rows.append({"unit_id": 1, "cycle": cycle, "sensor_1": 1.0})
    for cycle in range(1, 6):
        rows.append({"unit_id": 2, "cycle": cycle, "sensor_1": 100.0})
    return pd.DataFrame(rows)


def test_no_nans_in_output():
    """First-window rows yield NaN std; they must be back-filled, not left NaN."""
    out = add_rolling_features(_two_engines(), ["sensor_1"])
    assert not out[["sensor_1_roll_mean", "sensor_1_roll_std"]].isna().any().any()


def test_window_does_not_cross_engine_boundary():
    """Engine 2's first rolling mean must be 100, not contaminated by engine 1."""
    out = add_rolling_features(_two_engines(), ["sensor_1"])
    eng2 = out[out["unit_id"] == 2].sort_values("cycle")
    assert (eng2["sensor_1_roll_mean"] == 100.0).all()
    # constant signal -> zero volatility, never engine 1's values
    assert (eng2["sensor_1_roll_std"] == 0.0).all()


def test_rolling_mean_smooths_within_engine():
    """A 3-window trailing mean over [0,2,4,6,8] is [0,1,2,4,6]."""
    df = pd.DataFrame({"unit_id": [1] * 5, "cycle": range(1, 6),
                       "sensor_1": [0.0, 2.0, 4.0, 6.0, 8.0]})
    out = add_rolling_features(df, ["sensor_1"], window=3)
    assert out.sort_values("cycle")["sensor_1_roll_mean"].tolist() == [0.0, 1.0, 2.0, 4.0, 6.0]


def test_feature_columns_layout():
    """Each kept sensor expands to raw + roll_mean + roll_std, in order."""
    cols = feature_columns(["sensor_2", "sensor_3"])
    assert cols == [
        "sensor_2", "sensor_2_roll_mean", "sensor_2_roll_std",
        "sensor_3", "sensor_3_roll_mean", "sensor_3_roll_std",
    ]
