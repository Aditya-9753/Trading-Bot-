import pytest

from app.strategies.params import V1_1, V1_2, Side
from app.risk import risk_engine, position_sizer, stop_loss, daily_loss
from app.trading.execution.execution_engine import route, CostModel, NORMAL, TWAP, VWAP

P = V1_2


def test_risk_score_formula():
    ra = risk_engine.assess(vol_ratio=1.0, current_drawdown=0.10, conviction=0.8, p=P)
    assert ra.risk_vol == pytest.approx(0.5)
    assert ra.risk_dd == pytest.approx(0.5)            # 0.10 / 0.20
    assert ra.risk_confidence == pytest.approx(0.2)
    assert ra.risk_score == pytest.approx(0.4 * 0.5 + 0.35 * 0.5 + 0.25 * 0.2)


def test_risk_components_capped_at_one():
    ra = risk_engine.assess(vol_ratio=10, current_drawdown=0.9, conviction=0.0, p=P)
    assert ra.risk_score == pytest.approx(1.0)


def test_position_size_worked_example():
    # capital 1,00,000, risk 1% -> Rs 1000 at risk; ATR 10 -> SL distance 20 -> 50 shares base
    s = position_sizer.size(100_000, atr=10, conviction=0.8, risk_score=0.25, p=P)
    assert s.base_size == pytest.approx(50)
    assert s.final_size == pytest.approx(30)
    assert s.quantity == 30


def test_position_size_capped_by_cash():
    s = position_sizer.size(100_000, atr=1, conviction=1, risk_score=0, p=P, price=500, buying_power=10_000)
    assert s.capped_by_cash and s.quantity == 20


def test_short_conviction_v1_1_vs_v1_2():
    """Fix #4: v1.1 shrinks a strong short to CF=0.10; v1.2 is symmetric with longs."""
    cf_short, cf_long = (-0.8 + 1) / 2, (0.8 + 1) / 2
    assert risk_engine.conviction_factor(cf_short, Side.SHORT, V1_1) == pytest.approx(0.1)
    assert risk_engine.conviction_factor(cf_short, Side.SHORT, V1_2) == pytest.approx(0.9)
    assert risk_engine.conviction_factor(cf_long, Side.LONG, V1_2) == pytest.approx(0.9)


def test_levels_long_and_short():
    lv = stop_loss.initial_levels(Side.LONG, 100, 5, P)
    assert (lv.stop_loss, lv.take_profit) == (90, 120)
    sv = stop_loss.initial_levels(Side.SHORT, 100, 5, P)
    assert (sv.stop_loss, sv.take_profit) == (110, 80)


def test_trailing_only_tightens():
    assert stop_loss.tighten(Side.LONG, 90, 95) == 95
    assert stop_loss.tighten(Side.LONG, 95, 92) == 95
    assert stop_loss.tighten(Side.SHORT, 110, 105) == 105


def test_daily_loss_block():
    assert not daily_loss.is_blocked(100_000, 97_100, P)
    assert daily_loss.is_blocked(100_000, 97_000, P)


def test_execution_routing_threshold():
    assert route(10, 100, adv_value=1_000_000, p=P)[0] == NORMAL        # 0.1%
    assert route(200, 100, adv_value=1_000_000, p=P)[0] == TWAP         # 2%
    assert route(200, 100, adv_value=1_000_000, p=P, has_intraday_profile=True)[0] == VWAP


def test_costs_always_hurt():
    c = CostModel()
    assert c.fill_price(True, 100) > 100 and c.fill_price(False, 100) < 100
    assert c.fees(True, 100_000) > c.fees(False, 100_000) > 0     # stamp duty only on buy
