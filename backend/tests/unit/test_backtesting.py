from dataclasses import replace

import numpy as np
import pytest

from app.strategies.params import V1_1, V1_2, Side
from app.backtesting.engine import run_backtest
from app.trading.execution.execution_engine import CostModel

P = V1_2


def test_backtest_runs_and_equity_consistent(ohlcv):
    r = run_backtest(ohlcv, P, initial_capital=1_000_000)
    assert len(r.equity) == len(ohlcv)
    realized = sum(t.pnl for t in r.trades)
    assert r.equity.iloc[-1] == pytest.approx(1_000_000 + realized, rel=1e-9)


def test_entries_fill_at_next_open(ohlcv):
    """No look-ahead: an entry decided at close t fills at open t+1 (+ slippage)."""
    p = replace(P, entry_score=0.30, confirm_score=0.20)
    r = run_backtest(ohlcv, p)
    assert r.trades, "expected some trades with relaxed thresholds"
    c = CostModel()
    for t in r.trades:
        pos = ohlcv.index.get_loc(t.entry_time)
        assert pos > 0
        if t.policy == "NORMAL":
            assert t.entry_price == pytest.approx(c.fill_price(True, ohlcv["open"].iloc[pos]))


def test_zero_costs_beat_real_costs(ohlcv):
    p = replace(P, entry_score=0.30, confirm_score=0.20)
    free = CostModel(stt_pct=0, exchange_txn_pct=0, sebi_pct=0, stamp_buy_pct=0, slippage_bps=0, half_spread_bps=0,
                     impact_bps_per_pct_adv=0)
    a = run_backtest(ohlcv, p, costs=free).equity.iloc[-1]
    b = run_backtest(ohlcv, p).equity.iloc[-1]
    assert a >= b


def test_long_only_by_default(ohlcv):
    r = run_backtest(ohlcv, replace(P, entry_score=0.30, confirm_score=0.20))
    assert all(t.side == "LONG" for t in r.trades)


def test_initial_risk_within_budget(ohlcv):
    """Loss at the initial stop must be <= RiskBudget x equity (sizing only ever shrinks base size)."""
    r = run_backtest(ohlcv, replace(P, entry_score=0.30, confirm_score=0.20))
    for t in r.trades:
        assert abs(t.entry_price - t.initial_stop) * t.qty <= t.equity_at_entry * P.risk_budget + 1e-6


def test_v1_2_trades_at_spec_thresholds_v1_1_barely_does():
    """Fix #1 end-to-end: default thresholds, no relaxing."""
    from scripts.synthetic_data import make_ohlcv
    df = make_ohlcv(2000, 42)
    v11 = run_backtest(df, V1_1).metrics["trade_count"]
    v12 = run_backtest(df, V1_2).metrics["trade_count"]
    assert v11 <= 2 and v12 >= 10


def test_shorts_get_real_size_when_enabled():
    from scripts.synthetic_data import make_ohlcv
    df = make_ohlcv(2000, 3)
    r = run_backtest(df, replace(V1_2, allow_short=True))
    shorts = [t for t in r.trades if t.side == Side.SHORT]
    assert shorts, "expected short trades on synthetic downtrends"
    longs = [t for t in r.trades if t.side == Side.LONG]
    # risk taken per short is comparable to longs (v1.1 would make it ~5-10x smaller)
    rs = lambda ts: np.median([abs(t.entry_price - t.initial_stop) * t.qty / t.equity_at_entry for t in ts])
    assert rs(shorts) > 0.3 * rs(longs)


def test_version_mismatch_is_rejected(ohlcv):
    from app.strategies.built_in.hybrid_strategy import compute_features
    with pytest.raises(ValueError):
        run_backtest(ohlcv, V1_2, features=compute_features(ohlcv, V1_1))
