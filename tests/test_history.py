"""Tests for the per-cycle degradation histories (src/history.py)."""

import numpy as np
import pandas as pd
import pytest

from etl import RUL_CLIP
from history import build_history, true_rul_by_cycle


class ConstantModel:
    """Stand-in for the trained regressor: predicts a fixed RUL everywhere."""

    def __init__(self, value=50.0):
        self.value = value

    def predict(self, X):
        return np.full(len(X), self.value)


class FakeStore:
    """Storage double serving an in-memory test frame and RUL file."""

    def __init__(self, test_df, final_ruls):
        self.test_df = test_df
        self.final_ruls = final_ruls

    def read_parquet(self, rel):
        return self.test_df.copy()

    def read_csv(self, rel, **kw):
        return pd.DataFrame({"rul": self.final_ruls})


@pytest.fixture
def store():
    """Two engines with different lifetimes, one feature column."""
    rows = [{"unit_id": 1, "cycle": c, "f": 0.5} for c in range(1, 6)]
    rows += [{"unit_id": 2, "cycle": c, "f": 0.5} for c in range(1, 4)]
    return FakeStore(pd.DataFrame(rows), final_ruls=[10, 100])


@pytest.fixture
def bands():
    """One band spanning the whole range, ±10 cycles. Must cover every possible
    prediction: apply_conformal only writes to rows a band matches, so a gap
    would leave uninitialised interval values behind."""
    return [{"lo": 0.0, "hi": np.inf, "adj_lo": -10.0, "adj_hi": 10.0, "n": 100}]


def test_true_rul_counts_down_to_the_known_final_value():
    """The last cycle must equal the RUL the dataset ships; earlier cycles are
    that plus the cycles since — the reconstruction the chart plots as 'actual'."""
    engine = pd.DataFrame({"cycle": [1, 2, 3, 4, 5]})
    assert true_rul_by_cycle(engine, final_rul=10) == [14, 13, 12, 11, 10]


def test_true_rul_is_clipped_to_the_training_cap():
    """Actual and predicted must share the piecewise-linear scale, or the
    predicted-vs-actual overlay compares two different quantities."""
    engine = pd.DataFrame({"cycle": [1, 2, 3]})
    actuals = true_rul_by_cycle(engine, final_rul=RUL_CLIP)
    assert actuals == [RUL_CLIP, RUL_CLIP, RUL_CLIP]


def test_history_covers_every_cycle_of_every_engine(store, bands):
    histories = build_history(store, ConstantModel(), feats=["f"], bands=bands)
    assert set(histories) == {1, 2}
    assert [p["cycle"] for p in histories[1]["points"]] == [1, 2, 3, 4, 5]
    assert [p["cycle"] for p in histories[2]["points"]] == [1, 2, 3]


def test_history_summary_reflects_the_final_cycle(store, bands):
    """The record's headline fields must match the fleet snapshot, which is
    scored at the last observed cycle — otherwise card and chart disagree."""
    histories = build_history(store, ConstantModel(50.0), feats=["f"], bands=bands)
    assert histories[1]["current_cycle"] == 5
    assert histories[1]["predicted_rul"] == 50
    assert histories[1]["status"] == "WARNING"  # 30 <= 50 < 60


def test_each_engine_gets_its_own_true_rul(store, bands):
    """Engine ids index into RUL_FD001.txt by position; an off-by-one here would
    silently pair every engine with the wrong ground truth."""
    histories = build_history(store, ConstantModel(), feats=["f"], bands=bands)
    assert histories[1]["points"][-1]["actual_rul"] == 10
    assert histories[2]["points"][-1]["actual_rul"] == 100
