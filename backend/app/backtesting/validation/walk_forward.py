"""Robustness test, walk-forward and out-of-sample split (spec Section 17)."""
from dataclasses import replace
from itertools import product

import pandas as pd

from ...strategies.params import HybridParams, V1_2
from ...strategies.built_in.hybrid_strategy import compute_features
from ..engine import run_backtest

# Params that change the feature pipeline (need recompute); others only affect decisions.
_FEATURE_PARAMS = {"version", "momentum_horizon_scaling", "epsilon", "fast_ema", "slow_ema", "macd_fast", "macd_slow", "macd_signal", "momentum_lookback",
                   "rsi_window", "mr_window", "volume_window", "atr_period", "volratio_window",
                   "trend_threshold", "highvol_threshold", "adv_window"}


class _FeatureCache:
    def __init__(self, df):
        self.df, self.cache = df, {}

    def get(self, p: HybridParams):
        key = tuple(getattr(p, k) for k in sorted(_FEATURE_PARAMS))
        if key not in self.cache:
            self.cache[key] = compute_features(self.df, p)
        return self.cache[key]


def split_holdout(df: pd.DataFrame, holdout_frac: float = 0.2):
    """Development set and a fully held-out OOS set. Touch the holdout ONCE."""
    cut = int(len(df) * (1 - holdout_frac))
    return df.iloc[:cut], df.iloc[cut:]


def robustness_test(df, p: HybridParams = V1_2, params=("entry_score", "atr_stop_mult", "trend_threshold",
                    "highvol_threshold", "risk_budget"), multipliers=(0.8, 0.9, 1.0, 1.1, 1.2), **bt_kwargs) -> pd.DataFrame:
    """Perturb each parameter; large jumps between neighbours = cliff-edge sensitivity."""
    cache, rows = _FeatureCache(df), []
    for name in params:
        for m in multipliers:
            q = replace(p, **{name: getattr(p, name) * m})
            r = run_backtest(df, q, features=cache.get(q), start=p.warmup_bars, **bt_kwargs)
            rows.append({"param": name, "multiplier": m, "value": getattr(q, name), **r.metrics})
    return pd.DataFrame(rows)


def walk_forward(df, grid: dict, base: HybridParams = V1_2, train_bars: int = 500,
                 test_bars: int = 125, objective: str = "sharpe", min_trades: int = 3, **bt_kwargs):
    """Rolling re-optimisation on train window, evaluation on the next unseen window.

    Features are causal, so computing them on the full series introduces no look-ahead;
    trading is restricted to each window via start/end.
    """
    cache = _FeatureCache(df)
    names = list(grid)
    candidates = [replace(base, **dict(zip(names, vals))) for vals in product(*grid.values())]
    rows = []
    s = base.warmup_bars
    while s + train_bars + test_bars <= len(df):
        tr_end, te_end = s + train_bars, s + train_bars + test_bars
        best, best_val = None, float("-inf")
        for q in candidates:
            m = run_backtest(df, q, features=cache.get(q), start=s, end=tr_end, **bt_kwargs).metrics
            val = m.get(objective, float("-inf")) if m.get("trade_count", 0) >= min_trades else float("-inf")
            if val > best_val:
                best, best_val = q, val
        best = best or base
        test = run_backtest(df, best, features=cache.get(best), start=tr_end, end=te_end, **bt_kwargs).metrics
        rows.append({"train_start": df.index[s], "test_start": df.index[tr_end], "test_end": df.index[te_end - 1],
                     **{f"chosen_{k}": getattr(best, k) for k in names}, "train_" + objective: best_val,
                     **{f"test_{k}": v for k, v in test.items()}})
        s += test_bars
    return pd.DataFrame(rows)
