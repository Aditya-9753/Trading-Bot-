"""v1.1 vs v1.2 comparison + full validation sequence.

SYNTHETIC data proves the pipeline works; it says NOTHING about real-market profitability.
Usage:  python -m scripts.demo_backtest            (synthetic)
        python -m scripts.demo_backtest my.csv     (date,open,high,low,close,volume)
"""
import sys

import pandas as pd

from app.strategies.params import V1_1, V1_2
from app.strategies.built_in.hybrid_strategy import compute_features
from app.strategies.engine.signal_engine import entry_signals
from app.backtesting.engine import run_backtest
from app.backtesting.validation.walk_forward import split_holdout, walk_forward, robustness_test
from scripts.synthetic_data import make_ohlcv

KEYS = ["trade_count", "total_return", "cagr", "win_rate", "profit_factor", "sharpe", "max_drawdown",
        "turnover", "cost_drag_pct_of_start"]


def load(argv):
    if len(argv) > 1:
        df = pd.read_csv(argv[1], parse_dates=[0], index_col=0)
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()
    return make_ohlcv(n=2000, seed=42)


def diagnostics(df, p):
    f = compute_features(df, p)
    v = f.dropna()
    ok = v[v.regime != "HIGH_VOLATILITY"]
    return {"momentum_saturated": (v.momentum_score.abs() > 0.95).mean(),
            "bars_|S|>=entry": (ok.S.abs() >= p.entry_score).mean(),
            "BUY_candidates": int((entry_signals(f, p) == "BUY").sum())}


if __name__ == "__main__":
    pd.set_option("display.width", 140)
    df = load(sys.argv)
    dev, holdout = split_holdout(df, 0.2)

    print("=== 1. Signal diagnostics (dev set) ===")
    print(pd.DataFrame({"v1.1": diagnostics(dev, V1_1), "v1.2": diagnostics(dev, V1_2)}).round(3))

    print("\n=== 2. In-sample backtest (dev set, fees + slippage + spread) ===")
    res = {p.version: run_backtest(dev, p, start=p.warmup_bars).metrics for p in (V1_1, V1_2)}
    print(pd.DataFrame(res).loc[KEYS].round(4))

    print("\n=== 3. Parameter robustness, v1.2 (look for cliffs) ===")
    rb = robustness_test(dev, V1_2, params=("entry_score", "atr_stop_mult", "trend_threshold"))
    print(rb.pivot(index="multiplier", columns="param", values="sharpe").round(3))

    print("\n=== 4. Walk-forward, v1.2 (re-optimise entry_score each window) ===")
    wf = walk_forward(dev, {"entry_score": [0.45, 0.55, 0.65]}, V1_2, train_bars=500, test_bars=125)
    print(wf[["test_start", "chosen_entry_score", "test_trade_count", "test_total_return", "test_max_drawdown"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("Mean OOS window return:", round(wf["test_total_return"].mean(), 4))

    print("\n=== 5. Final holdout (touch ONCE), v1.2 baseline ===")
    ho = pd.concat([dev.iloc[-V1_2.warmup_bars:], holdout])
    print(pd.Series(run_backtest(ho, V1_2, start=V1_2.warmup_bars).metrics).loc[KEYS].round(4).to_string())
