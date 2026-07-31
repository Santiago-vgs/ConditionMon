"""Tests for the evaluation suite's output contract (src/insights.py).

The dashboard's model-health view reads this structure straight from the API, so
its shape is a contract, not an implementation detail.
"""

import numpy as np
import pandas as pd
import pytest

from insights import phm08_score, threshold_sweep


@pytest.fixture
def val():
    """Three engines run to failure, with a prediction column that counts down
    in step with the true remaining life."""
    rows = []
    for unit, life in ((1, 40), (2, 55), (3, 30)):
        for cycle in range(1, life + 1):
            rows.append({
                "unit_id": unit,
                "cycle": cycle,
                "pred": float(life - cycle),
            })
    return pd.DataFrame(rows)


def test_sweep_returns_a_shared_x_axis_and_per_ratio_curves(val):
    sweep = threshold_sweep(val, "pred")
    assert set(sweep) == {"taus", "ratios"}
    assert sweep["taus"][0] == 5 and sweep["taus"][-1] == 80
    # every cost ratio is plotted against that same x-axis
    for ratio, r in sweep["ratios"].items():
        assert set(r) == {"best_tau", "cost", "curve"}
        assert len(r["curve"]) == len(sweep["taus"]), f"ratio {ratio} curve misaligned"


def test_sweep_best_tau_is_the_curve_minimum(val):
    """best_tau and cost must agree with the exported curve — the dashboard
    draws the curve and annotates the minimum, so a mismatch shows up as a
    marker floating off the line."""
    sweep = threshold_sweep(val, "pred")
    taus = sweep["taus"]
    for r in sweep["ratios"].values():
        lowest = min(r["curve"])
        assert r["cost"] == pytest.approx(lowest, abs=0.01)
        assert r["best_tau"] == taus[r["curve"].index(lowest)]


def test_ratios_are_ordered_and_distinct_where_failures_are_missed(val):
    """A costlier failure can never make an under-alerting policy look cheaper.
    At the lowest threshold, cost must rise with the failure multiplier."""
    sweep = threshold_sweep(val, "pred")
    at_lowest_tau = [
        (int(ratio), r["curve"][0]) for ratio, r in sweep["ratios"].items()
    ]
    at_lowest_tau.sort()
    costs = [c for _, c in at_lowest_tau]
    assert costs == sorted(costs), "cost should increase with failure cost"


def test_phm08_penalises_late_calls_harder_than_early_ones():
    """The asymmetry is the whole reason this metric is used instead of RMSE:
    predicting more life than an engine has is the dangerous direction."""
    truth = np.array([50.0])
    late = phm08_score(truth, np.array([70.0]))   # predicted 20 cycles too much
    early = phm08_score(truth, np.array([30.0]))  # predicted 20 cycles too little
    assert late > early
