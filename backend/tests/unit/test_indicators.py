import numpy as np
import pandas as pd
import pytest

from app.strategies.indicators import core
from app.strategies.params import V1_1, V1_2
from app.strategies.built_in.hybrid_strategy import compute_features, validate_ohlcv, DataQualityError
from scripts.synthetic_data import make_ohlcv

SCORES = ["trend_score", "momentum_score", "rsi_score", "mean_reversion_score", "reversion_score",
          "volume_score", "volatility_score", "S"]


def test_true_range_includes_gaps():
    df = pd.DataFrame({"open": [10, 14], "high": [11, 15], "low": [9, 13.5], "close": [10, 14.5], "volume": [1, 1]})
    tr = core.true_range(df)
    assert tr.iloc[0] == 2 and tr.iloc[1] == 5


def test_rsi_bounds_and_extremes():
    assert core.rsi(pd.Series(np.arange(1, 60, dtype=float))).dropna().eq(100).all()
    r = core.rsi(pd.Series(100 + np.random.default_rng(1).standard_normal(300).cumsum())).dropna()
    assert r.between(0, 100).all()


@pytest.mark.parametrize("p", [V1_1, V1_2])
def test_all_scores_bounded(ohlcv, p):
    f = compute_features(ohlcv, p)
    for c in SCORES:
        assert f[c].dropna().between(-1, 1).all(), c
    assert f["confidence"].dropna().between(0, 100).all()


@pytest.mark.parametrize("p", [V1_1, V1_2])
def test_scores_are_price_scale_invariant(ohlcv, p):
    scaled = ohlcv.copy()
    scaled[["open", "high", "low", "close"]] *= 100
    a, b = compute_features(ohlcv, p), compute_features(scaled, p)
    for c in SCORES:
        pd.testing.assert_series_equal(a[c], b[c], check_exact=False, rtol=1e-6, atol=1e-9)
    assert (a["regime"] == b["regime"]).all()


@pytest.mark.parametrize("p", [V1_1, V1_2])
def test_features_are_causal(ohlcv, p):
    full, part = compute_features(ohlcv, p), compute_features(ohlcv.iloc[:600], p)
    pd.testing.assert_series_equal(full["S"].iloc[:600], part["S"], check_exact=False, rtol=1e-9)


def test_v1_2_momentum_not_saturated():
    """Fix #2: v1.1 momentum sits at +-1 on most bars; v1.2 is a real z-score."""
    df = make_ohlcv(2000, 42)
    sat = lambda p: (compute_features(df, p)["momentum_score"].dropna().abs() > 0.95).mean()
    assert sat(V1_1) > 0.5
    assert sat(V1_2) < 0.2


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 99])
def test_v1_2_entry_threshold_reachable(seed):
    """Fix #1: |S| >= 0.55 must be reachable outside HIGH_VOLATILITY."""
    f = compute_features(make_ohlcv(2000, seed), V1_2).dropna()
    ok = f[f.regime != "HIGH_VOLATILITY"]
    assert (ok["S"].abs() >= V1_2.entry_score).mean() > 0.03


def test_v1_2_volatility_does_not_move_S(ohlcv):
    """Fix #3: changing volatility_score must not change S in v1.2."""
    from app.strategies.engine.signal_engine import signal_score
    f = compute_features(ohlcv, V1_2)
    g = f.copy(); g["volatility_score"] = 0.99
    pd.testing.assert_series_equal(signal_score(f, V1_2), signal_score(g, V1_2))


def test_warmup_has_no_signal(ohlcv):
    assert compute_features(ohlcv)["S"].iloc[:V1_2.volratio_window].isna().all()


@pytest.mark.parametrize("mutate", [
    lambda d: d.iloc.__setitem__((50, 3), np.nan),
    lambda d: d.iloc.__setitem__((50, 3), -1.0),
])
def test_validation_rejects_bad_data(ohlcv, mutate):
    bad = ohlcv.copy(); mutate(bad)
    with pytest.raises(DataQualityError):
        validate_ohlcv(bad)


def test_validation_rejects_duplicate_timestamps(ohlcv):
    with pytest.raises(DataQualityError):
        validate_ohlcv(pd.concat([ohlcv.iloc[:10], ohlcv.iloc[9:20]]))
