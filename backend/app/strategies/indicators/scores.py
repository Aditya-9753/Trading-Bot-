"""Component scores, each in [-1, +1] (spec Section 5)."""
import numpy as np

from . import core


def trend_score(close, atr_s, trend_base, p):
    """5.1 - T1 is D_T from the regime engine, passed in and reused (not recomputed)."""
    line, sig = core.macd(close, p.macd_fast, p.macd_slow, p.macd_signal)
    t2 = np.tanh((line - sig) / atr_s)
    return 0.60 * trend_base + 0.40 * t2


def momentum_return(close, p):
    return close / close.shift(p.momentum_lookback) - 1


def momentum_score(close, p):
    """5.2 - volatility-adjusted momentum.

    v1.1: tanh(R_20 / STD(R,20))           -> saturates at +-1 on most bars (20-bar return vs 1-bar std)
    v1.2: tanh(R_20 / (STD(R,20)*sqrt(20))) -> horizon-consistent, a true 20-bar z-score
    """
    n = p.momentum_lookback
    std_r = core.returns(close).rolling(n, min_periods=n).std()
    if p.momentum_horizon_scaling:
        std_r = std_r * np.sqrt(n)
    return np.tanh(momentum_return(close, p) / (std_r + p.epsilon))


def rsi_score(close, p):
    """5.3 - contrarian: oversold -> positive."""
    return (50 - core.rsi(close, p.rsi_window)) / 50


def mean_reversion_score(close, p):
    """5.4 - Std here is correctly a *price* std (Z-score of price)."""
    mean = core.sma(close, p.mr_window)
    std = close.rolling(p.mr_window, min_periods=p.mr_window).std()
    return -np.tanh((close - mean) / (std + p.epsilon))


def reversion_score(rsi_s, mr_s):
    """v1.2 - single reversion view: equal blend of the two highly-correlated contrarian scores."""
    return 0.5 * rsi_s + 0.5 * mr_s


def volume_score(volume, close, p):
    """5.5 - confirms direction of momentum."""
    rvol = volume / core.sma(volume, p.volume_window)
    return np.tanh(rvol - 1) * np.sign(momentum_return(close, p))


def volatility_score(vol_ratio_s):
    """5.6 - directional component in v1.1; display/diagnostic only in v1.2."""
    return np.tanh(vol_ratio_s - 1)
