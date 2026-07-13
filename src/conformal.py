"""Distribution-free prediction intervals via split conformal calibration.

Why: a point RUL ("40 cycles left") hides how wrong the model might be, and a
maintenance planner schedules against the *worst case*, not the average. Split
conformal turns held-out residuals into an interval with a guaranteed error
rate — no distributional assumptions, works on top of any model.

How: on engines the model never trained on, measure residual = true - predicted.
The middle 90% of those residuals tells us how far off the model typically is;
add that band around every new prediction. Because RUL error is much larger far
from failure than near it (heteroscedastic), we calibrate *per band of
predicted RUL* (a "Mondrian" split) instead of one global band — otherwise
near-failure intervals would be uselessly wide.
"""

from __future__ import annotations

import numpy as np

# band edges over the *predicted* RUL — matches the alert thresholds
BIN_EDGES = (0.0, 30.0, 60.0, 90.0, np.inf)
RUL_CAP = 125  # labels are clipped here, so no honest interval can exceed it


def fit_conformal(y_true, y_pred, alpha: float = 0.10) -> list[dict]:
    """Calibrate per-band residual quantiles on held-out data.

    Returns one dict per band: {lo, hi, adj_lo, adj_hi, n}. adj_lo/adj_hi are
    the signed corrections such that [pred+adj_lo, pred+adj_hi] covers the true
    value with probability >= 1-alpha (finite-sample corrected quantiles).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    res = y_true - y_pred

    bands = []
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        mask = (y_pred >= lo) & (y_pred < hi)
        r = np.sort(res[mask])
        n = len(r)
        if n < 20:  # too thin to calibrate — fall back to global residuals
            r, n = np.sort(res), len(res)
        # finite-sample correction: rank ceil((n+1)*q)/n instead of plain q
        q_hi = min(1.0, np.ceil((n + 1) * (1 - alpha / 2)) / n)
        q_lo = max(0.0, np.floor((n + 1) * (alpha / 2)) / n)
        bands.append({
            "lo": float(lo), "hi": float(hi),
            "adj_lo": float(np.quantile(r, q_lo)),
            "adj_hi": float(np.quantile(r, q_hi)),
            "n": int(mask.sum()),
        })
    return bands


def apply_conformal(bands: list[dict], y_pred) -> tuple[np.ndarray, np.ndarray]:
    """Turn point predictions into [low, high] intervals, clipped to [0, cap]."""
    y_pred = np.asarray(y_pred, dtype=float)
    lo = np.empty_like(y_pred)
    hi = np.empty_like(y_pred)
    for band in bands:
        mask = (y_pred >= band["lo"]) & (y_pred < band["hi"])
        lo[mask] = y_pred[mask] + band["adj_lo"]
        hi[mask] = y_pred[mask] + band["adj_hi"]
    return np.clip(lo, 0, RUL_CAP), np.clip(hi, 0, RUL_CAP)


def coverage(bands: list[dict], y_true, y_pred) -> float:
    """Fraction of true values that land inside their interval."""
    lo, hi = apply_conformal(bands, y_pred)
    y = np.clip(np.asarray(y_true, dtype=float), 0, RUL_CAP)
    return float(np.mean((y >= lo) & (y <= hi)))
