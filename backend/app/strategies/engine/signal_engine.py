"""Signal score, confidence and entry rules (spec Sections 6-8)."""
import numpy as np
import pandas as pd

from ..params import Regime, HybridParams


def weight_frame(regime: pd.Series, p: HybridParams) -> pd.DataFrame:
    comps = list(p.components)
    nan_row = {c: np.nan for c in comps}
    rows = [p.weights.get(r, nan_row) for r in regime]
    return pd.DataFrame(rows, index=regime.index, columns=comps)


def signal_score(features: pd.DataFrame, p: HybridParams) -> pd.Series:
    """S_t = sum(w_i * score_i), weights selected by regime and version. NaN during warmup."""
    comps = list(p.components)
    comp = features[[f"{c}_score" for c in comps]].copy()
    comp.columns = comps
    return (weight_frame(features["regime"], p) * comp).sum(axis=1, min_count=len(comps)).rename("S")


def confidence(s: pd.Series) -> pd.Series:
    return 50 * (s + 1)


def component_contributions(features: pd.DataFrame, p: HybridParams) -> pd.DataFrame:
    """w_i * score_i per bar - feeds the frontend ComponentScoreBreakdown."""
    comps = list(p.components)
    comp = features[[f"{c}_score" for c in comps]].copy()
    comp.columns = comps
    return weight_frame(features["regime"], p) * comp


def entry_signal(s: float, s_prev: float, regime: str, p: HybridParams) -> str:
    """Section 8 incl. two-bar confirmation. Returns BUY / SELL / HOLD."""
    if regime in (Regime.HIGH_VOLATILITY, Regime.WARMUP) or s != s or s_prev != s_prev:
        return "HOLD"
    if s >= p.entry_score and s_prev > p.confirm_score:
        return "BUY"
    if s <= -p.entry_score and s_prev < -p.confirm_score:
        return "SELL"
    return "HOLD"


def entry_signals(features: pd.DataFrame, p: HybridParams) -> pd.Series:
    s, prev, reg = features["S"], features["S"].shift(1), features["regime"]
    return pd.Series([entry_signal(a, b, r, p) for a, b, r in zip(s, prev, reg)], index=features.index, name="entry")
