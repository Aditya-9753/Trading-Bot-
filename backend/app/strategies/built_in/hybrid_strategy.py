"""Hybrid pipeline: OHLCV -> scores -> regime -> S_t -> confidence."""
import numpy as np
import pandas as pd

from ..params import HybridParams, V1_2
from ..indicators import core, scores
from ..engine import regime_engine, signal_engine

REQUIRED = ("open", "high", "low", "close", "volume")


class DataQualityError(ValueError):
    pass


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise DataQualityError(f"missing columns: {missing}")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise DataQualityError("index must be strictly increasing (sorted, no duplicate timestamps)")
    if df[list(REQUIRED)].isna().any().any():
        # PRD Section 16: flag gaps, never silently interpolate
        raise DataQualityError("OHLCV contains NaN - clean/flag the data before running")
    if (df[["open", "high", "low", "close"]] <= 0).any().any() or (df["volume"] < 0).any():
        raise DataQualityError("non-positive prices or negative volume")
    bad = (df["high"] < df[["open", "close", "low"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))
    if bad.any():
        raise DataQualityError(f"{int(bad.sum())} candles have inconsistent high/low")
    return df


def compute_features(df: pd.DataFrame, p: HybridParams = V1_2) -> pd.DataFrame:
    validate_ohlcv(df)
    c, v = df["close"], df["volume"]
    f = pd.DataFrame(index=df.index)

    f["atr"] = core.atr(df, p.atr_period)
    f["d_t"] = (core.ema(c, p.fast_ema) - core.ema(c, p.slow_ema)) / f["atr"]
    f["trend_base"] = np.tanh(f["d_t"])          # computed ONCE, reused as T1
    f["vol_ratio"] = core.vol_ratio(c, f["atr"], p.volratio_window)
    f["regime"] = regime_engine.classify(f["trend_base"], f["vol_ratio"], p)

    f["trend_score"] = scores.trend_score(c, f["atr"], f["trend_base"], p)
    f["momentum_score"] = scores.momentum_score(c, p)
    f["rsi_score"] = scores.rsi_score(c, p)
    f["mean_reversion_score"] = scores.mean_reversion_score(c, p)
    f["reversion_score"] = scores.reversion_score(f["rsi_score"], f["mean_reversion_score"])
    f["volume_score"] = scores.volume_score(v, c, p)
    f["volatility_score"] = scores.volatility_score(f["vol_ratio"])

    f["S"] = signal_engine.signal_score(f, p)
    f["confidence"] = signal_engine.confidence(f["S"])
    f["confidence_factor"] = f["confidence"] / 100
    f["adv_value"] = (c * v).rolling(p.adv_window, min_periods=p.adv_window).mean()
    f.attrs["algorithm_version"] = p.version
    return f
