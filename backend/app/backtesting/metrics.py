"""Performance metrics (spec Section 17 table)."""
import math

import numpy as np
import pandas as pd


def compute_metrics(equity: pd.Series, trades: list, bars_per_year: int = 252,
                    traded_value: float = 0.0, slippage_cost: float = 0.0) -> dict:
    if len(equity) < 2:
        return {"trade_count": len(trades)}
    e0, e1 = float(equity.iloc[0]), float(equity.iloc[-1])
    total_return = e1 / e0 - 1
    years = len(equity) / bars_per_year
    cagr = (e1 / e0) ** (1 / years) - 1 if years > 0 and e1 > 0 else float("nan")
    rets = equity.pct_change().dropna()
    sd = rets.std()
    sharpe = float(rets.mean() / sd * math.sqrt(bars_per_year)) if sd and sd > 0 else 0.0
    max_dd = float((equity / equity.cummax() - 1).min())

    pnls = np.array([t.pnl for t in trades], float)
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
    gross_loss = -losses.sum()
    fees = sum(t.entry_fees + t.exit_fees for t in trades)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "win_rate": float(len(wins) / len(pnls)) if len(pnls) else float("nan"),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else (float("inf") if len(wins) else float("nan")),
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "avg_trade": float(pnls.mean()) if len(pnls) else float("nan"),
        "trade_count": int(len(pnls)),
        "turnover": float(traded_value / equity.mean()) if equity.mean() > 0 else float("nan"),
        "fees_paid": float(fees),
        "slippage_cost": float(slippage_cost),
        "cost_drag_pct_of_start": float((fees + slippage_cost) / e0),
    }
