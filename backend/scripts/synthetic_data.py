"""Synthetic OHLCV with regime switches - for testing the pipeline ONLY, not for judging profitability."""
import numpy as np
import pandas as pd


def make_ohlcv(n: int = 1500, seed: int = 42, start_price: float = 1000.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # (drift, vol) per regime block: uptrend, chop, downtrend, crash-vol, recovery ...
    regimes = [(0.0012, 0.010), (0.0, 0.008), (-0.0010, 0.011), (0.0, 0.030), (0.0015, 0.012), (0.0, 0.009)]
    drift, vol = np.empty(n), np.empty(n)
    i = 0
    while i < n:
        d, v = regimes[rng.integers(len(regimes))]
        L = int(rng.integers(60, 200))
        drift[i:i + L], vol[i:i + L] = d, v
        i += L
    r = drift + vol * rng.standard_normal(n)
    close = start_price * np.exp(np.cumsum(r))
    open_ = np.r_[start_price, close[:-1]] * np.exp(vol * 0.3 * rng.standard_normal(n))
    hi = np.maximum(open_, close) * np.exp(np.abs(vol * 0.6 * rng.standard_normal(n)))
    lo = np.minimum(open_, close) * np.exp(-np.abs(vol * 0.6 * rng.standard_normal(n)))
    volume = (1e6 * np.exp(0.4 * rng.standard_normal(n)) * (1 + 20 * np.abs(r))).round()
    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": volume}, index=idx)
