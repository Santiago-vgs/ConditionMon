"""Score every cycle of every test engine -> per-engine degradation histories.

Why this exists: `train.py` scores each test engine at its *final* observed
cycle only, which collapses the whole run into a single number. A maintenance
planner doesn't just want "117 cycles left" — they want to see whether that
estimate has been falling steadily for 80 cycles or jumped last week. That's a
trajectory, and a trajectory needs every cycle scored, not just the last one.

Output: one JSON per engine under `predictions/history/engine_<id>.json`, so the
dashboard fetches ~7 KB to draw one chart instead of the ~1 MB the whole fleet
would cost. Each point carries the point estimate, its 90% conformal interval,
and — because FD001 ships true end-of-life RUL for the test set — the actual
RUL, which turns the chart into a visible predicted-vs-actual check.

Runs standalone off the artifacts `train.py` already wrote (no retraining):

    python src/history.py          # local data/ -> data/predictions/history/
    python src/history.py --s3     # s3://<bucket>/predictions/history/
"""

from __future__ import annotations

import argparse

import pandas as pd

from conformal import apply_conformal
from etl import RUL_CLIP
from features import CYCLE_COL, ID_COL, feature_columns
from storage import PREDICTIONS, PROCESSED, RAW, Storage, from_args
from train import status_for

HISTORY_PREFIX = f"{PREDICTIONS}/history"


def true_rul_by_cycle(engine: pd.DataFrame, final_rul: int) -> list[int]:
    """Reconstruct the actual RUL at every observed cycle of a test engine.

    RUL_FD001.txt gives the true RUL at each engine's *last* observed cycle.
    Every earlier cycle is that value plus the cycles since — exact, not
    estimated. Clipped at 125 to match the piecewise-linear label `etl.py`
    trained against, so predicted and actual are on the same scale.
    """
    last_cycle = int(engine[CYCLE_COL].max())
    return [
        min(RUL_CLIP, final_rul + (last_cycle - int(c)))
        for c in engine[CYCLE_COL]
    ]


def build_history(
    store: Storage,
    model,
    feats: list[str],
    bands: list[dict],
) -> dict[int, dict]:
    """Score all cycles of all test engines, grouped into per-engine records."""
    test = store.read_parquet(f"{PROCESSED}/test.parquet").sort_values(
        [ID_COL, CYCLE_COL]
    )
    # one predict() over the whole frame is far cheaper than 100 small ones
    test = test.assign(pred=model.predict(test[feats]))
    lo, hi = apply_conformal(bands, test["pred"].to_numpy())
    test = test.assign(rul_low=lo, rul_high=hi)

    # true RUL at each engine's final cycle, in engine-id order (1..100)
    final_ruls = store.read_csv(
        f"{RAW}/RUL_FD001.txt", header=None, names=["rul"]
    )["rul"].tolist()

    histories: dict[int, dict] = {}
    for engine_id, grp in test.groupby(ID_COL, sort=True):
        actuals = true_rul_by_cycle(grp, int(final_ruls[int(engine_id) - 1]))
        points = [
            {
                "cycle": int(c),
                "predicted_rul": int(round(float(p))),
                "rul_low": int(round(float(l))),
                "rul_high": int(round(float(h))),
                "actual_rul": int(a),
            }
            for c, p, l, h, a in zip(
                grp[CYCLE_COL], grp["pred"], grp["rul_low"], grp["rul_high"], actuals
            )
        ]
        last = points[-1]
        histories[int(engine_id)] = {
            "engine_id": int(engine_id),
            "current_cycle": last["cycle"],
            "predicted_rul": last["predicted_rul"],
            "status": status_for(last["predicted_rul"]),
            "points": points,
        }
    return histories


def write_history(store: Storage, histories: dict[int, dict]) -> None:
    for engine_id, record in histories.items():
        store.write_json(record, f"{HISTORY_PREFIX}/engine_{engine_id}.json")


def run(store: Storage) -> None:
    print(f"Storage: {store}")
    model = store.load(f"{PROCESSED}/model.joblib")
    bands = store.load(f"{PROCESSED}/conformal.joblib")
    kept_sensors = store.load(f"{PROCESSED}/kept_sensors.joblib")
    feats = feature_columns(kept_sensors)

    print("Scoring every cycle of every test engine:")
    histories = build_history(store, model, feats, bands)
    write_history(store, histories)

    n_points = sum(len(h["points"]) for h in histories.values())
    print(
        f"  wrote {len(histories)} engine histories "
        f"({n_points} scored cycles) -> {HISTORY_PREFIX}/"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3", action="store_true", help="read/write S3 instead of local")
    parser.add_argument("--bucket", help="override S3 bucket name")
    args = parser.parse_args()
    run(from_args(args.s3, args.bucket))


if __name__ == "__main__":
    main()
