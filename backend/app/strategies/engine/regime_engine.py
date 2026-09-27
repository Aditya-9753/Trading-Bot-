"""Regime classification (spec Section 4.3)."""
import numpy as np
import pandas as pd

from ..params import Regime, HybridParams


def classify(trend_base: pd.Series, vol_ratio: pd.Series, p: HybridParams) -> pd.Series:
    valid = trend_base.notna() & vol_ratio.notna()
    trending = (trend_base.abs() > p.trend_threshold) & (vol_ratio < p.highvol_threshold)
    highvol = vol_ratio >= p.highvol_threshold
    out = np.select([~valid, trending, highvol],
                    [Regime.WARMUP, Regime.TRENDING, Regime.HIGH_VOLATILITY],
                    default=Regime.SIDEWAYS)
    return pd.Series(out, index=trend_base.index, name="regime")


def classify_one(trend_base: float, vol_ratio: float, p: HybridParams) -> str:
    if trend_base != trend_base or vol_ratio != vol_ratio:  # NaN
        return Regime.WARMUP
    if abs(trend_base) > p.trend_threshold and vol_ratio < p.highvol_threshold:
        return Regime.TRENDING
    if vol_ratio >= p.highvol_threshold:
        return Regime.HIGH_VOLATILITY
    return Regime.SIDEWAYS
