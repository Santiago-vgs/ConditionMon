"""Tests for the split-conformal interval logic (src/conformal.py)."""

import numpy as np

from conformal import RUL_CAP, apply_conformal, coverage, fit_conformal


def _calibration_sample(n=2000, noise=10.0, seed=0):
    """Synthetic calibration set: predictions across the RUL range with
    symmetric noise of known scale."""
    rng = np.random.default_rng(seed)
    y_pred = rng.uniform(0, 125, n)
    y_true = y_pred + rng.normal(0, noise, n)
    return y_true, y_pred


def test_intervals_cover_at_the_requested_rate():
    """The whole point of conformal: ~90% of fresh points land inside."""
    bands = fit_conformal(*_calibration_sample(seed=0), alpha=0.10)
    y_new, p_new = _calibration_sample(seed=1)
    assert coverage(bands, y_new, p_new) >= 0.85  # small slack for sampling noise


def test_intervals_are_clipped_to_valid_rul():
    """RUL below 0 or above the label cap is physically meaningless."""
    bands = fit_conformal(*_calibration_sample(), alpha=0.10)
    lo, hi = apply_conformal(bands, np.array([0.0, 5.0, 120.0, 125.0]))
    assert (lo >= 0).all() and (hi <= RUL_CAP).all()


def test_wider_noise_gives_wider_intervals():
    """Calibration must reflect the model's actual error scale."""
    tight = fit_conformal(*_calibration_sample(noise=5.0), alpha=0.10)
    loose = fit_conformal(*_calibration_sample(noise=20.0), alpha=0.10)
    p = np.array([60.0])
    (lo_t, hi_t), (lo_l, hi_l) = apply_conformal(tight, p), apply_conformal(loose, p)
    assert (hi_l - lo_l) > (hi_t - lo_t)


def test_thin_band_falls_back_to_global_residuals():
    """With almost no calibration points in a band, per-band quantiles would be
    meaningless — the fit should fall back to the global residual pool."""
    rng = np.random.default_rng(2)
    # nearly all predictions in the healthy band, a handful near failure
    y_pred = np.concatenate([rng.uniform(90, 125, 500), rng.uniform(0, 30, 5)])
    y_true = y_pred + rng.normal(0, 10, y_pred.size)
    bands = fit_conformal(y_true, y_pred, alpha=0.10)
    critical = bands[0]
    assert critical["n"] < 20  # the band really was thin
    assert critical["adj_hi"] - critical["adj_lo"] > 0  # and still got a usable width
