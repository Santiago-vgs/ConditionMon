"""Tests for the leakage-safe split and the status rule (src/train.py)."""

import pandas as pd

from train import (
    MAINTENANCE_BELOW,
    VAL_FROM_ENGINE,
    WARNING_BELOW,
    engine_split,
    status_for,
)


def test_engine_split_is_disjoint_by_engine():
    """The core leakage guard: no engine appears in both train and validation."""
    df = pd.DataFrame({"unit_id": [e for e in range(1, 101) for _ in range(3)]})
    tr, val = engine_split(df)
    tr_ids = set(tr["unit_id"])
    val_ids = set(val["unit_id"])
    assert tr_ids.isdisjoint(val_ids)
    assert max(tr_ids) < VAL_FROM_ENGINE <= min(val_ids)
    assert tr_ids | val_ids == set(range(1, 101))  # no rows lost


def test_status_thresholds_at_boundaries():
    """Boundaries must match the rule documented for the dashboard/config.js."""
    assert status_for(MAINTENANCE_BELOW - 1) == "MAINTENANCE_REQUIRED"
    assert status_for(MAINTENANCE_BELOW) == "WARNING"        # 30 is not maintenance
    assert status_for(WARNING_BELOW - 1) == "WARNING"
    assert status_for(WARNING_BELOW) == "OK"                 # 60 is OK
    assert status_for(125) == "OK"


def test_status_is_one_of_three_labels():
    assert {status_for(r) for r in range(0, 130)} == {
        "MAINTENANCE_REQUIRED", "WARNING", "OK",
    }
