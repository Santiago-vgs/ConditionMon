"""Generate the explanatory figures used in docs/UNDERSTANDING.md.

Run from the repo root:  python docs/figures.py
Outputs PNGs into docs/img/. Pure read-only on the data/artifacts already
produced by etl.py / train.py.
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
from features import feature_columns  # noqa: E402

import joblib  # noqa: E402

IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

COLS = (
    ["unit_id", "cycle"]
    + [f"setting_{i}" for i in (1, 2, 3)]
    + [f"sensor_{i}" for i in range(1, 22)]
)
raw = pd.read_csv(ROOT / "data/raw/train_FD001.txt", sep=r"\s+", header=None, names=COLS)


# 1. Sensor trends: trending (keep) vs flat (drop) -------------------------
def fig_sensor_trends() -> None:
    engines = [1, 20, 50, 90]
    trend = ["sensor_2", "sensor_4", "sensor_11", "sensor_15"]
    flat = ["sensor_1", "sensor_5", "sensor_16", "sensor_18"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 6.5))
    for row, group, tag in [(0, trend, "TRENDS → keep"), (1, flat, "FLAT → drop")]:
        for j, s in enumerate(group):
            ax = axes[row, j]
            for e in engines:
                sub = raw[raw.unit_id == e]
                ax.plot(sub.cycle, sub[s], lw=1)
            ax.set_title(f"{s}  ({tag})", fontsize=10)
            ax.set_xlabel("cycle")
    fig.suptitle("Why we drop sensors: top row carries a degradation signal, bottom row is constant", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMG / "sensor_trends.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# 2. Engine lifetimes vary --------------------------------------------------
def fig_lifetimes() -> None:
    lifetimes = raw.groupby("unit_id")["cycle"].max()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(lifetimes, bins=25, edgecolor="black", color="#4C72B0")
    ax.axvline(lifetimes.mean(), color="red", ls="--", label=f"mean = {lifetimes.mean():.0f}")
    ax.set_title("Engine lifetimes vary (FD001 train) — so RUL must be per-engine")
    ax.set_xlabel("failure cycle")
    ax.set_ylabel("# engines")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "lifetime_dist.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# 3. RUL clipping at 125 ----------------------------------------------------
def fig_rul_clip() -> None:
    e = 24  # a longer-lived engine so the clip is visible
    sub = raw[raw.unit_id == e].copy()
    life = sub.cycle.max()
    rul_raw = life - sub.cycle
    rul_clip = rul_raw.clip(upper=125)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(sub.cycle, rul_raw, label="raw RUL = max(cycle) − cycle", lw=2, color="#999999")
    ax.plot(sub.cycle, rul_clip, label="clipped at 125 (what we train on)", lw=2, color="#C44E52")
    ax.axhline(125, ls=":", color="black", lw=1)
    ax.set_title(f"RUL label for engine {e}: clipping flattens the 'healthy' early region")
    ax.set_xlabel("cycle")
    ax.set_ylabel("Remaining Useful Life")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "rul_clipping.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# 4. Feature importances (trained model) ------------------------------------
def fig_importance() -> None:
    model = joblib.load(ROOT / "data/processed/model.joblib")
    kept = joblib.load(ROOT / "data/processed/kept_sensors.joblib")
    feats = feature_columns(kept)
    imp = pd.Series(model.feature_importances_, index=feats).sort_values()[-12:]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(imp.index, imp.values, color="#55A868")
    ax.set_title("Top 12 features (Random Forest) — rolling means of trending sensors dominate")
    ax.set_xlabel("importance")
    fig.tight_layout()
    fig.savefig(IMG / "feature_importance.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# 5. Predicted vs true RUL on the held-out test set -------------------------
def fig_pred_vs_true() -> None:
    pred = pd.DataFrame(json.load(open(ROOT / "data/predictions/predictions.json")))
    pred = pred.sort_values("engine_id")
    true = pd.read_csv(ROOT / "data/raw/RUL_FD001.txt", header=None)[0].values
    true_clip = np.clip(true, None, 125)
    p = pred.predicted_rul.values
    rmse = np.sqrt(np.mean((p - true_clip) ** 2))
    fig, ax = plt.subplots(figsize=(6.2, 6))
    ax.scatter(true_clip, p, alpha=0.7, color="#4C72B0", edgecolor="white")
    lim = [0, 130]
    ax.plot(lim, lim, "k--", lw=1, label="perfect prediction (y = x)")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("true RUL (clipped @125)")
    ax.set_ylabel("predicted RUL")
    ax.set_title(f"Test set: predicted vs true RUL\nRMSE = {rmse:.1f} cycles")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "pred_vs_true.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# 6. Status breakdown of the fleet -----------------------------------------
def fig_status() -> None:
    pred = pd.DataFrame(json.load(open(ROOT / "data/predictions/predictions.json")))
    order = ["MAINTENANCE_REQUIRED", "WARNING", "OK"]
    colors = {"MAINTENANCE_REQUIRED": "#C44E52", "WARNING": "#DD8452", "OK": "#55A868"}
    counts = pred.status.value_counts().reindex(order).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index, counts.values, color=[colors[s] for s in counts.index])
    for i, v in enumerate(counts.values):
        ax.text(i, v + 0.5, int(v), ha="center")
    ax.set_title("Fleet status from predictions.json (RUL<30 → maintenance, <60 → warning)")
    ax.set_ylabel("# engines")
    fig.tight_layout()
    fig.savefig(IMG / "status_breakdown.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_sensor_trends()
    fig_lifetimes()
    fig_rul_clip()
    fig_importance()
    fig_pred_vs_true()
    fig_status()
    print("wrote figures to", IMG)
