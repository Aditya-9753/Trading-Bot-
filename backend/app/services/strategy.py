"""User-tunable parameters of the fixed, versioned Hybrid engine + backtest runner."""
import hashlib
import json
import math
from dataclasses import replace

import numpy as np
import pandas as pd

from ..backtesting.engine import run_backtest
from ..backtesting.validation.walk_forward import robustness_test, walk_forward
from ..strategies.built_in.hybrid_strategy import compute_features
from ..strategies.engine.signal_engine import component_contributions
from ..strategies.params import V1_1, V1_2, HybridParams

VERSIONS = {"1.2": V1_2, "1.1": V1_1}

# name -> (min, max, type, label, help)
TUNABLE = {
    "entry_score": (0.30, 0.90, float, "Entry score", "|S| needed to enter (2-bar confirmed)"),
    "confirm_score": (0.10, 0.80, float, "Confirmation score", "Previous bar must be beyond this"),
    "long_exit": (-0.80, 0.20, float, "Long exit score", "Exit a long when S falls below this"),
    "atr_stop_mult": (0.5, 5.0, float, "Stop distance (× ATR)", "Initial stop = entry − k·ATR"),
    "reward_risk": (0.5, 6.0, float, "Reward : risk", "Target = entry + RR × stop distance"),
    "risk_budget": (0.001, 0.03, float, "Risk per trade", "Fraction of capital risked per trade"),
    "trend_threshold": (0.10, 0.80, float, "Trend threshold", "|trend base| above this = TRENDING"),
    "highvol_threshold": (1.1, 3.0, float, "High-vol threshold", "VolRatio above this = HIGH_VOLATILITY (no entries)"),
    "fast_ema": (5, 50, int, "Fast EMA", "Bars"),
    "slow_ema": (20, 200, int, "Slow EMA", "Bars"),
}


class ParamError(ValueError):
    pass


def build_params(version: str = "1.2", overrides: dict | None = None) -> HybridParams:
    if version not in VERSIONS:
        raise ParamError(f"unknown algorithm version {version!r}; available: {', '.join(VERSIONS)}")
    clean = {}
    for k, v in (overrides or {}).items():
        if k not in TUNABLE:
            raise ParamError(f"parameter {k!r} cannot be changed")
        lo, hi, typ, *_ = TUNABLE[k]
        try:
            v = typ(v)
        except (TypeError, ValueError):
            raise ParamError(f"{k} must be a number")
        if isinstance(v, float) and not math.isfinite(v):
            raise ParamError(f"{k} must be finite")
        if not lo <= v <= hi:
            raise ParamError(f"{k} must be between {lo} and {hi}")
        clean[k] = v
    p = replace(VERSIONS[version], **clean)
    if p.fast_ema >= p.slow_ema:
        raise ParamError("fast_ema must be smaller than slow_ema")
    if p.confirm_score > p.entry_score:
        raise ParamError("confirm_score cannot exceed entry_score")
    return p


def params_hash(version: str, overrides: dict) -> str:
    return hashlib.sha256(json.dumps({"v": version, "p": overrides}, sort_keys=True).encode()).hexdigest()


def defaults(version: str = "1.2") -> dict:
    p = VERSIONS[version]
    return {k: getattr(p, k) for k in TUNABLE}


def _num(v):
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)


def clean_dict(d: dict) -> dict:
    return {k: _num(v) for k, v in d.items()}


def signal_series(df: pd.DataFrame, p: HybridParams, bars: int = 200) -> dict:
    f = compute_features(df, p)
    contrib = component_contributions(f, p)
    tail = f.iloc[-bars:]
    last = f.iloc[-1]
    return {
        "algorithm_version": p.version,
        "components": list(p.components),
        "weights": p.weights,
        "series": [{"t": t.isoformat(), "S": _num(r["S"]), "regime": r["regime"], "close": _num(r["close"]) if "close" in r else None}
                   for t, r in tail.iterrows()],
        "latest": {
            "t": f.index[-1].isoformat(), "S": _num(last["S"]), "regime": last["regime"],
            "confidence": _num(last["confidence"]), "atr": _num(last["atr"]), "vol_ratio": _num(last["vol_ratio"]),
            "scores": {c: _num(last[f"{c}_score"]) for c in p.components},
            "contributions": {k: _num(v) for k, v in contrib.iloc[-1].items()},
        },
        "thresholds": {"entry": p.entry_score, "confirm": p.confirm_score, "long_exit": p.long_exit},
    }


def _downsample(series: pd.Series, n: int = 400) -> list:
    step = max(1, math.ceil(len(series) / n))
    s = series.iloc[::step]
    if s.index[-1] != series.index[-1]:
        s = pd.concat([s, series.iloc[[-1]]])
    return [{"t": t.isoformat(), "v": round(float(v), 2)} for t, v in s.items()]


def run(df: pd.DataFrame, version: str, overrides: dict, initial_capital: float,
        do_walk_forward: bool = False, do_robustness: bool = False) -> dict:
    p = build_params(version, overrides)
    if len(df) < p.warmup_bars + 60:
        raise ParamError(f"not enough history: need at least {p.warmup_bars + 60} bars, have {len(df)}")
    res = run_backtest(df, p, initial_capital=initial_capital, start=p.warmup_bars)
    eq = res.equity
    bench = df["close"].loc[eq.index]
    bench = bench / bench.iloc[0] * initial_capital
    trades = [{
        "side": t.side, "entry_time": pd.Timestamp(t.entry_time).isoformat(), "entry_price": _num(t.entry_price),
        "exit_time": pd.Timestamp(t.exit_time).isoformat() if t.exit_time is not None else None,
        "exit_price": _num(t.exit_price), "qty": int(t.qty), "pnl": _num(t.pnl), "exit_reason": t.exit_reason,
        "regime": t.regime, "score": _num(t.score), "policy": t.policy,
    } for t in res.trades]
    out = {
        "metrics": clean_dict(res.metrics),
        "equity_curve": _downsample(eq),
        "benchmark_curve": _downsample(bench),
        "trades": trades,
        "risk_events": [clean_dict(e) if isinstance(e, dict) else str(e) for e in res.risk_events][:200],
        "bars": int(len(eq)), "start": eq.index[0].isoformat(), "end": eq.index[-1].isoformat(),
        "walk_forward": None, "robustness": None,
    }
    if do_walk_forward:
        n = len(df) - p.warmup_bars
        train, test = max(150, int(n * 0.45)), max(40, int(n * 0.15))
        grid = {"entry_score": sorted({round(p.entry_score - 0.05, 2), p.entry_score, round(p.entry_score + 0.05, 2)}),
                "atr_stop_mult": sorted({round(p.atr_stop_mult - 0.5, 2), p.atr_stop_mult, round(p.atr_stop_mult + 0.5, 2)})}
        wf = walk_forward(df, grid, base=p, train_bars=train, test_bars=test, initial_capital=initial_capital)
        out["walk_forward"] = [clean_dict(r) for r in wf.to_dict("records")]
    if do_robustness:
        rb = robustness_test(df, p, initial_capital=initial_capital)
        out["robustness"] = [clean_dict(r) for r in rb.to_dict("records")]
    return out
