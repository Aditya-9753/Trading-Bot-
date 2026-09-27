"""Event-driven backtester for Hybrid v1.1.

Timing convention (no look-ahead): signals are decided on the CLOSE of bar t and filled at the
OPEN of bar t+1. Stops/targets are checked intrabar from bar high/low; if both are touched in the
same bar the stop is assumed to hit first (conservative). Gaps through a level fill at the open.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..strategies.params import HybridParams, Side, V1_2
from ..strategies.built_in.hybrid_strategy import compute_features
from ..strategies.engine.signal_engine import entry_signal
from ..risk import risk_engine, position_sizer, stop_loss, daily_loss
from ..trading.execution.execution_engine import CostModel, route
from .metrics import compute_metrics


@dataclass
class Trade:
    side: str
    entry_time: object
    entry_price: float
    qty: int
    stop: float
    target: float
    policy: str
    regime: str
    score: float
    risk_score: float
    entry_fees: float
    extreme: float
    initial_stop: float = float("nan")
    equity_at_entry: float = float("nan")
    exit_time: object = None
    exit_price: float = float("nan")
    exit_fees: float = 0.0
    exit_reason: str = ""
    pnl: float = float("nan")


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: list
    features: pd.DataFrame
    metrics: dict
    risk_events: list = field(default_factory=list)

    def trades_frame(self) -> pd.DataFrame:
        return pd.DataFrame([t.__dict__ for t in self.trades])


def _session_key(ts, i):
    return ts.date() if hasattr(ts, "date") else i


def run_backtest(df: pd.DataFrame, p: HybridParams = V1_2, costs: CostModel = CostModel(),
                 initial_capital: float = 1_000_000.0, start: int | None = None, end: int | None = None,
                 bars_per_year: int = 252, features: pd.DataFrame | None = None) -> BacktestResult:
    f = features if features is not None else compute_features(df, p)
    if f.attrs.get("algorithm_version", p.version) != p.version:
        raise ValueError("features were computed with a different algorithm version")
    n = len(df)
    start = max(start or 0, 0)
    end = min(end if end is not None else n, n)
    idx = df.index
    O, H, L, C = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    S, REG = f["S"].to_numpy(float), f["regime"].to_numpy()
    ATR, VR = f["atr"].to_numpy(float), f["vol_ratio"].to_numpy(float)
    CF, ADV = f["confidence_factor"].to_numpy(float), f["adv_value"].to_numpy(float)

    cash, pos, pending = initial_capital, None, None
    trades, risk_events, eq_vals, eq_idx = [], [], [], []
    peak = equity = initial_capital
    session, day_start, blocked = None, initial_capital, False
    traded_value = slippage_cost = 0.0

    def close_position(i, ref_price, reason):
        nonlocal cash, pos, traded_value, slippage_cost
        is_buy = pos.side == Side.SHORT
        px = costs.fill_price(is_buy, ref_price)
        value = px * pos.qty
        fee = costs.fees(is_buy, value)
        cash += (-value if is_buy else value) - fee
        traded_value += value
        slippage_cost += abs(px - ref_price) * pos.qty
        gross = (px - pos.entry_price) * pos.qty * (1 if pos.side == Side.LONG else -1)
        pos.exit_time, pos.exit_price, pos.exit_fees, pos.exit_reason = idx[i], px, fee, reason
        pos.pnl = gross - pos.entry_fees - fee
        trades.append(pos)
        pos = None

    for i in range(start, end):
        key = _session_key(idx[i], i)
        if key != session:
            session, day_start, blocked = key, equity, False

        # 1) execute order decided at previous close
        if pending is not None:
            kind, arg, j = pending
            pending = None
            if kind == "EXIT" and pos is not None:
                close_position(i, O[i], arg)
            elif kind == "ENTER" and pos is None and not blocked:
                side = arg
                conv = risk_engine.conviction_factor(CF[j], side, p)
                dd = 1 - equity / peak if peak > 0 else 0.0
                ra = risk_engine.assess(VR[j], dd, conv, p)
                buying_power = cash if side == Side.LONG else equity
                sz = position_sizer.size(equity, ATR[j], conv, ra.risk_score, p, O[i], buying_power * p.max_buying_power_use)
                if sz.quantity > 0:
                    policy, ratio = route(sz.quantity, O[i], ADV[j], p)
                    is_buy = side == Side.LONG
                    px = costs.fill_price(is_buy, O[i], policy, ratio)
                    value = px * sz.quantity
                    fee = costs.fees(is_buy, value)
                    cash += (-value if is_buy else value) - fee
                    traded_value += value
                    slippage_cost += abs(px - O[i]) * sz.quantity
                    lv = stop_loss.initial_levels(side, px, ATR[j], p)
                    pos = Trade(side, idx[i], px, sz.quantity, lv.stop_loss, lv.take_profit, policy,
                                REG[j], S[j], ra.risk_score, fee, px, lv.stop_loss, equity)

        # 2) intrabar stop / target
        if pos is not None:
            long = pos.side == Side.LONG
            if long:
                if O[i] <= pos.stop:   close_position(i, O[i], "STOP_GAP")
                elif O[i] >= pos.target: close_position(i, O[i], "TARGET_GAP")
                elif L[i] <= pos.stop: close_position(i, pos.stop, "STOP")
                elif H[i] >= pos.target: close_position(i, pos.target, "TARGET")
            else:
                if O[i] >= pos.stop:   close_position(i, O[i], "STOP_GAP")
                elif O[i] <= pos.target: close_position(i, O[i], "TARGET_GAP")
                elif H[i] >= pos.stop: close_position(i, pos.stop, "STOP")
                elif L[i] <= pos.target: close_position(i, pos.target, "TARGET")
            if pos is not None:  # trail for NEXT bar using this bar's extreme
                pos.extreme = max(pos.extreme, H[i]) if long else min(pos.extreme, L[i])
                pos.stop = stop_loss.tighten(pos.side, pos.stop, stop_loss.trailing_stop(pos.side, pos.extreme, ATR[i], p))

        # 3) mark to market
        if pos is not None:
            equity = cash + (pos.qty * C[i] if pos.side == Side.LONG else -pos.qty * C[i])
        else:
            equity = cash
        peak = max(peak, equity)
        eq_vals.append(equity); eq_idx.append(idx[i])

        if not blocked and daily_loss.is_blocked(day_start, equity, p):
            blocked = True
            risk_events.append({"time": idx[i], "event": "DAILY_LOSS_BLOCK", "equity": equity})

        # 4) decide for next bar
        if i + 1 >= end:
            continue
        if pos is not None:
            if pos.side == Side.LONG and S[i] < p.long_exit:
                pending = ("EXIT", "SIGNAL_REVERSAL", i)
            elif pos.side == Side.SHORT and S[i] > p.short_exit:
                pending = ("EXIT", "SIGNAL_REVERSAL", i)
        elif not blocked and i > 0:
            sig = entry_signal(S[i], S[i - 1], REG[i], p)
            if sig == "BUY":
                pending = ("ENTER", Side.LONG, i)
            elif sig == "SELL" and p.allow_short:
                pending = ("ENTER", Side.SHORT, i)

    if pos is not None:
        close_position(end - 1, C[end - 1], "END_OF_TEST")
        eq_vals[-1] = cash

    equity_s = pd.Series(eq_vals, index=eq_idx, name="equity")
    m = compute_metrics(equity_s, trades, bars_per_year, traded_value, slippage_cost)
    m["algorithm_version"] = p.version
    return BacktestResult(equity_s, trades, f, m, risk_events)
