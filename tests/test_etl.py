"""Tests for the ETL label + sensor-drop logic (src/etl.py)."""

import pandas as pd

from etl import ALL_SENSORS, RUL_CLIP, add_rul, find_dead_sensors


def _frame(lifetimes: dict[int, int]) -> pd.DataFrame:
    """Build a minimal raw-like frame: {engine_id: n_cycles}."""
    rows = []
    for unit, n in lifetimes.items():
        for cycle in range(1, n + 1):
            rows.append({"unit_id": unit, "cycle": cycle})
    return pd.DataFrame(rows)


def test_final_cycle_rul_is_zero_per_engine():
    """Every engine's last training row is the failure point -> RUL must be 0."""
    df = add_rul(_frame({1: 3, 2: 5}))
    finals = df.groupby("unit_id")["RUL"].min()
    assert (finals == 0).all()


def test_rul_counts_down_from_failure():
    """RUL = max_cycle - cycle before clipping."""
    df = add_rul(_frame({1: 4}))  # short life, no clipping in play
    assert df.sort_values("cycle")["RUL"].tolist() == [3, 2, 1, 0]


def test_rul_is_clipped_at_the_cap():
    """An engine living far past the cap is flat-capped early in life."""
    df = add_rul(_frame({1: 300}))
    assert df["RUL"].max() == RUL_CLIP
    # late-life rows are below the cap and still count down to 0
    assert df.sort_values("cycle")["RUL"].iloc[-1] == 0


def test_clip_is_configurable():
    df = add_rul(_frame({1: 100}), clip=10)
    assert df["RUL"].max() == 10


def test_find_dead_sensors_flags_constant_columns():
    """A sensor with ~0 std carries no signal and must be flagged."""
    df = _frame({1: 5, 2: 5})
    for s in ALL_SENSORS:
        df[s] = 1.0  # all constant -> all dead
    df.loc[df.index[0], "sensor_2"] = 999.0  # give sensor_2 some variance
    dead = find_dead_sensors(df)
    assert "sensor_2" not in dead
    assert "sensor_1" in dead
    assert len(dead) == len(ALL_SENSORS) - 1
