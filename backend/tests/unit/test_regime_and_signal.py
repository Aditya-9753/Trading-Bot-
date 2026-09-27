import pandas as pd
import pytest

from app.strategies.params import V1_1, V1_2, Regime, WEIGHTS_V1_1, WEIGHTS_V1_2, HybridParams
from app.strategies.engine.regime_engine import classify, classify_one
from app.strategies.engine.signal_engine import entry_signal


@pytest.mark.parametrize("weights", [WEIGHTS_V1_1, WEIGHTS_V1_2])
def test_weight_columns_sum_to_one(weights):
    for reg, w in weights.items():
        assert sum(w.values()) == pytest.approx(1.0), reg


def test_unknown_version_rejected():
    with pytest.raises(ValueError):
        HybridParams(version="9.9")


def test_v1_2_has_no_directional_volatility_and_merged_reversion():
    assert "volatility" not in V1_2.components
    assert "reversion" in V1_2.components and "rsi" not in V1_2.components
    assert V1_2.weights[Regime.TRENDING]["reversion"] <= 0.05


@pytest.mark.parametrize("tb,vr,expected", [
    (0.5, 1.0, Regime.TRENDING),
    (-0.5, 1.0, Regime.TRENDING),
    (0.5, 1.5, Regime.HIGH_VOLATILITY),
    (0.1, 2.0, Regime.HIGH_VOLATILITY),
    (0.35, 1.0, Regime.SIDEWAYS),
    (0.1, 1.0, Regime.SIDEWAYS),
    (float("nan"), 1.0, Regime.WARMUP),
])
def test_regime_rules(tb, vr, expected):
    assert classify_one(tb, vr, V1_2) == expected
    assert classify(pd.Series([tb]), pd.Series([vr]), V1_2).iloc[0] == expected


def test_entry_requires_confirmation():
    P = V1_2
    assert entry_signal(0.60, 0.35, Regime.TRENDING, P) == "BUY"
    assert entry_signal(0.60, 0.30, Regime.TRENDING, P) == "HOLD"
    assert entry_signal(-0.60, -0.31, Regime.SIDEWAYS, P) == "SELL"
    assert entry_signal(0.54, 0.50, Regime.TRENDING, P) == "HOLD"


def test_no_entry_in_high_volatility():
    assert entry_signal(0.9, 0.9, Regime.HIGH_VOLATILITY, V1_2) == "HOLD"
