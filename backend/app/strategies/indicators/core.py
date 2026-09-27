"""Base indicators (spec Section 3). All functions are causal: value at t uses data <= t only."""
import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def returns(close: pd.Series) -> pd.Series:
    """R_t = C_t / C_(t-1) - 1"""
    return close / close.shift(1) - 1


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    parts = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1)
    return parts.max(axis=1)  # first bar falls back to H-L


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR_t = EMA(TR, 14). Zero ATR (flat prices) -> NaN so downstream divisions stay safe."""
    return ema(true_range(df), n).replace(0.0, np.nan)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI with Wilder smoothing of average gain / average loss."""
    d = close.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    r = 100 - 100 / (1 + gain / loss)
    r = r.mask((loss == 0) & (gain > 0), 100.0)
    r = r.mask((loss == 0) & (gain == 0), 50.0)
    return r


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    return line, line.ewm(span=signal, adjust=False, min_periods=signal).mean()


def vol_ratio(close: pd.Series, atr_s: pd.Series, window: int = 100) -> pd.Series:
    """VolRatio = (ATR/C) / Median(ATR/C over last `window` periods) - Section 4.2"""
    natr = atr_s / close
    return natr / natr.rolling(window, min_periods=window).median()
