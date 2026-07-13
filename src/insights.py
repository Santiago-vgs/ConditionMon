"""Decision-grade evaluation of the RUL model — beyond a single RMSE number.

Four analyses a real predictive-maintenance team would run before trusting a
model with scheduling decisions:

    1. Error by RUL band     — where is the model accurate, where is it noise?
    2. Conformal intervals   — 90% ranges, coverage PROVEN on the test set,
                               plus NASA's official asymmetric PHM08 score.
    3. Cost-optimal policy   — sweep the alert threshold under a cost model
                               (unscheduled failure >> scheduled maintenance)
                               and backtest the policy over full engine lives.
    4. Drift check (PSI)     — would we notice if incoming data stopped
                               looking like training data?

Run from repo root (after etl.py + train.py):
    python src/insights.py

Writes figures to docs/img/ and a metrics summary to docs/insights_metrics.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from conformal import RUL_CAP, apply_conformal, fit_conformal  # noqa: E402
from features import feature_columns  # noqa: E402
from storage import PROCESSED, Storage, from_args  # noqa: E402
from train import ID_COL, CYCLE_COL, TARGET, VAL_FROM_ENGINE, engine_split, rmse  # noqa: E402

IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

RED, ORANGE, GREEN, BLUE, GRAY = "#FF3B30", "#FF9500", "#34C759", "#0071e3", "#8e8e93"


# ---------------------------------------------------------------------------
# 1. Error by RUL band — the honest picture behind one global RMSE
# ---------------------------------------------------------------------------
def error_by_band(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    bands = [(0, 30, "0–30\n(critical)"), (30, 60, "30–60"), (60, 90, "60–90"),
             (90, 126, "90–125\n(healthy)")]
    out = {}
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    labels, values = [], []
    for lo, hi, label in bands:
        m = (y_true >= lo) & (y_true < hi)
        out[f"{lo}-{hi}"] = round(rmse(y_true[m], y_pred[m]), 2)
        labels.append(label)
        values.append(out[f"{lo}-{hi}"])
    colors = [RED, ORANGE, GRAY, GRAY]
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.4, f"{v:.1f}",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("RMSE (cycles)")
    ax.set_xlabel("true RUL band")
    ax.set_title("The model is sharpest where it matters: near failure")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "error_by_rul_band.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 2. Conformal intervals on the test fleet + PHM08 score
# ---------------------------------------------------------------------------
def phm08_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """NASA's official PHM08 metric: over-predicting RUL (engine dies before
    you service it) is penalised ~3x harder than under-predicting (you service
    early). RMSE treats both mistakes the same; this metric encodes the real
    asymmetry of the domain."""
    d = y_pred - y_true
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def test_intervals(bands: list[dict], y_test: np.ndarray, pred_test: np.ndarray) -> dict:
    lo, hi = apply_conformal(bands, pred_test)
    y_cmp = np.clip(y_test, 0, RUL_CAP)  # labels are capped, so is the truth we compare to
    inside = (y_cmp >= lo) & (y_cmp <= hi)

    order = np.argsort(pred_test)
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.vlines(x, lo[order], hi[order], color=BLUE, alpha=0.35, lw=2.2,
              label="90% conformal interval")
    ax.scatter(x, pred_test[order], s=12, color=BLUE, label="predicted RUL")
    ax.scatter(x, y_cmp[order], s=16,
               c=[GREEN if k else RED for k in inside[order]], zorder=3,
               label="true RUL (green = inside)")
    ax.set_xlabel("test engines, sorted by predicted RUL")
    ax.set_ylabel("RUL (cycles)")
    ax.set_title(f"90% intervals on the 100 unseen test engines — "
                 f"empirical coverage {inside.mean():.0%}")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "conformal_intervals.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    width = hi - lo
    return {
        "coverage": round(float(inside.mean()), 3),
        "mean_width_critical": round(float(width[pred_test < 30].mean()), 1),
        "mean_width_healthy": round(float(width[pred_test >= 90].mean()), 1),
    }


# ---------------------------------------------------------------------------
# 3. Cost-optimal alert threshold + fleet backtest
# ---------------------------------------------------------------------------
# It takes time to act on an alert: route the aircraft to a maintenance base,
# reserve a shop slot, stage parts. An alert with less lead time than this is
# operationally a failure — you knew, but you couldn't do anything about it.
# Without this constraint the sweep degenerates to "alert at the last second".
MIN_ACTIONABLE_LEAD = 10  # cycles


def simulate_policy(val: pd.DataFrame, pred_col: str, tau: float) -> dict:
    """Replay each held-out engine's full life against the policy 'pull the
    engine the first time predicted RUL <= tau'. Because C-MAPSS engines are
    run to failure, the trade is lead time (safety margin) vs wasted life
    (cycles thrown away by pulling early)."""
    saved_leads, too_late = [], 0
    for _, g in val.groupby(ID_COL):
        g = g.sort_values(CYCLE_COL)
        end = g[CYCLE_COL].iloc[-1]
        hit = g[g[pred_col] <= tau]
        # true cycles remaining at the moment the alert fired (none -> 0 lead)
        lead = int(end - hit[CYCLE_COL].iloc[0]) if not hit.empty else 0
        if lead >= MIN_ACTIONABLE_LEAD:
            saved_leads.append(lead)
        else:
            too_late += 1  # alert too late (or never) to schedule maintenance
    return {"leads": saved_leads, "missed": too_late, "n": val[ID_COL].nunique()}


def threshold_sweep(val: pd.DataFrame, pred_col: str) -> dict:
    """Expected cost per engine vs threshold. Units: one scheduled maintenance
    visit = 1. An unscheduled in-service failure costs C_fail visits; every
    cycle of life thrown away by pulling the engine early costs 0.02 visits
    (waste a 50-cycle margin ~= pay for one extra shop visit)."""
    taus = np.arange(5, 81, 1)
    c_waste = 0.02
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    results = {}
    for c_fail, color in [(10, GREEN), (50, ORANGE), (100, RED)]:
        costs = []
        for tau in taus:
            sim = simulate_policy(val, pred_col, tau)
            cost = (sim["missed"] * c_fail
                    + (sim["n"] - sim["missed"]) * 1.0
                    + c_waste * sum(sim["leads"]))
            costs.append(cost / sim["n"])
        costs = np.array(costs)
        best = int(taus[np.argmin(costs)])
        results[c_fail] = {"best_tau": best, "cost": round(float(costs.min()), 2)}
        ax.plot(taus, costs, color=color, lw=2, label=f"failure = {c_fail}x maintenance")
        ax.scatter([best], [costs.min()], color=color, zorder=3)
        ax.annotate(f"τ={best}", (best, costs.min()), textcoords="offset points",
                    xytext=(6, 8), fontsize=9, color=color)
    ax.axvline(30, color=GRAY, ls="--", lw=1, alpha=0.6)
    ax.text(30.5, ax.get_ylim()[1] * 0.92, "current alert\nthreshold (30)",
            fontsize=8.5, color=GRAY)
    ax.set_xlabel("alert threshold τ (predicted RUL, cycles)")
    ax.set_ylabel("expected cost per engine (maintenance visits)")
    ax.set_title("Choosing the alert threshold by cost, not by gut feel")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "cost_threshold_sweep.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return results


def backtest_figure(val: pd.DataFrame, pred_col: str, tau: int) -> dict:
    sim = simulate_policy(val, pred_col, tau)
    leads = np.array(sim["leads"])
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.hist(leads, bins=np.arange(0, leads.max() + 6, 5), color=BLUE, alpha=0.85,
            edgecolor="white")
    ax.axvline(np.median(leads), color=RED, lw=2,
               label=f"median lead time = {np.median(leads):.0f} cycles")
    ax.axvspan(0, MIN_ACTIONABLE_LEAD, color=RED, alpha=0.08)
    ax.set_xlabel("true cycles remaining when the alert fired (lead time)")
    ax.set_ylabel("engines")
    ax.set_title(f"Backtest at τ={tau}: {sim['n'] - sim['missed']}/{sim['n']} failures "
                 f"caught with ≥{MIN_ACTIONABLE_LEAD} cycles to act")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "backtest_leadtime.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return {
        "tau": tau,
        "caught": sim["n"] - sim["missed"],
        "n": sim["n"],
        "median_lead": int(np.median(leads)),
        "min_lead": int(leads.min()),
        "max_lead": int(leads.max()),
    }


# ---------------------------------------------------------------------------
# 4. Drift monitoring — Population Stability Index per sensor
# ---------------------------------------------------------------------------
def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """PSI = sum (p_actual - p_expected) * ln(p_actual / p_expected) over
    quantile bins of the training data. Rule of thumb: <0.10 stable,
    0.10-0.25 investigate, >0.25 significant shift."""
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def drift_check(train: pd.DataFrame, test: pd.DataFrame, sensors: list[str]) -> dict:
    scores = {s: psi(train[s].to_numpy(), test[s].to_numpy()) for s in sensors}
    ordered = dict(sorted(scores.items(), key=lambda kv: -kv[1]))
    fig, ax = plt.subplots(figsize=(8.5, 5))
    names = list(ordered)
    vals = [ordered[n] for n in names]
    colors = [RED if v > 0.25 else ORANGE if v > 0.10 else GREEN for v in vals]
    ax.barh(names[::-1], vals[::-1], color=colors[::-1])
    ax.axvline(0.10, color=ORANGE, ls="--", lw=1)
    ax.axvline(0.25, color=RED, ls="--", lw=1)
    ax.set_xlabel("PSI (train vs test)")
    ax.set_title("Drift check: is the data the model sees still the data it learned from?")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "drift_psi.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return {k: round(v, 3) for k, v in ordered.items()}


# ---------------------------------------------------------------------------
def main() -> None:
    store: Storage = from_args(False)
    df = store.read_parquet(f"{PROCESSED}/train.parquet")
    test = store.read_parquet(f"{PROCESSED}/test.parquet")
    kept = store.load(f"{PROCESSED}/kept_sensors.joblib")
    model = store.load(f"{PROCESSED}/model.joblib")
    feats = feature_columns(kept)

    _, val = engine_split(df)
    val = val.copy()
    val["pred"] = model.predict(val[feats])
    y_val, p_val = val[TARGET].to_numpy(float), val["pred"].to_numpy(float)

    print("\n1. RMSE by true-RUL band (validation engines):")
    band_rmse = error_by_band(y_val, p_val)
    for k, v in band_rmse.items():
        print(f"    RUL {k:>7}: {v:.2f}")

    # test-set truth: RUL_FD001.txt gives true remaining life at each engine's last cycle
    y_test = pd.read_csv(ROOT / "data/raw/RUL_FD001.txt", header=None)[0].to_numpy(float)
    last = test.sort_values(CYCLE_COL).groupby(ID_COL).tail(1).sort_values(ID_COL)
    pred_test = model.predict(last[feats]).astype(float)

    print("\n2. Conformal 90% intervals (calibrated on val, verified on test):")
    bands = fit_conformal(y_val, p_val, alpha=0.10)
    conf = test_intervals(bands, y_test, pred_test)
    print(f"    empirical coverage on 100 unseen engines: {conf['coverage']:.0%}")
    print(f"    mean interval width: {conf['mean_width_critical']} cycles (critical) "
          f"vs {conf['mean_width_healthy']} (healthy)")

    score = phm08_score(np.clip(y_test, 0, RUL_CAP), pred_test)
    print(f"    NASA PHM08 score (test, lower=better): {score:.0f} "
          f"({score / len(y_test):.2f}/engine)")

    print("\n3. Cost-optimal alert threshold (sweep on validation engines):")
    sweep = threshold_sweep(val, "pred")
    for c_fail, r in sweep.items():
        print(f"    failure {c_fail:>3}x maintenance -> best τ={r['best_tau']}, "
              f"cost {r['cost']}/engine")
    tau_star = sweep[50]["best_tau"]

    print(f"\n   Backtest at τ={tau_star}:")
    bt = backtest_figure(val, "pred", tau_star)
    print(f"    caught {bt['caught']}/{bt['n']} failures, "
          f"median lead {bt['median_lead']} cycles "
          f"(min {bt['min_lead']}, max {bt['max_lead']})")

    print("\n4. Drift (PSI train vs test, kept sensors):")
    drift = drift_check(df, test, [f"sensor_{i}" for i in range(1, 22)
                                   if f"sensor_{i}" in kept])
    worst = list(drift.items())[:3]
    print(f"    worst 3: " + ", ".join(f"{k}={v}" for k, v in worst))

    metrics = {
        "rmse_by_band": band_rmse,
        "conformal": conf,
        "phm08_total": round(score, 1),
        "threshold_sweep": {str(k): v for k, v in sweep.items()},
        "backtest": bt,
        "psi": drift,
    }
    out = ROOT / "docs" / "insights_metrics.json"
    out.write_text(json.dumps(metrics, indent=2))
    print(f"\nWrote 5 figures to docs/img/ and metrics to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
