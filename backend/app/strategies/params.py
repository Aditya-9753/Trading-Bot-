"""Parameter registry for the TradeBot Hybrid Algorithm (spec Section 18).

Two versions live side by side, per the project rule "a change is a new version, never a silent edit":
  * V1_1 - spec-literal baseline, kept for comparison / regression.
  * V1_2 - fixes the issues found while implementing v1.1 (see CHANGELOG_v1_2.md). DEFAULT.
"""
from dataclasses import dataclass, replace


class Regime:
    WARMUP = "WARMUP"
    TRENDING = "TRENDING"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class Side:
    LONG = "LONG"
    SHORT = "SHORT"


# ---- v1.1 (spec Section 6) --------------------------------------------------
COMPONENTS_V1_1 = ("trend", "momentum", "rsi", "mean_reversion", "volume", "volatility")
WEIGHTS_V1_1 = {
    Regime.TRENDING:        {"trend": .35, "momentum": .25, "rsi": .10, "mean_reversion": .10, "volume": .10, "volatility": .10},
    Regime.SIDEWAYS:        {"trend": .10, "momentum": .15, "rsi": .25, "mean_reversion": .30, "volume": .10, "volatility": .10},
    Regime.HIGH_VOLATILITY: {"trend": .20, "momentum": .15, "rsi": .15, "mean_reversion": .15, "volume": .10, "volatility": .25},
}

# ---- v1.2 -------------------------------------------------------------------
# * RSI + Mean-Reversion merged into one "reversion" component (they were ~0.87 correlated).
# * Volatility removed from the DIRECTIONAL score (it has no direction); it still acts through
#   the regime engine, Risk_vol and the ATR stop distance.
# * Reversion weight ~0 in TRENDING so contrarian signals stop cancelling the trend.
COMPONENTS_V1_2 = ("trend", "momentum", "reversion", "volume")
WEIGHTS_V1_2 = {
    Regime.TRENDING:        {"trend": .45, "momentum": .35, "reversion": .05, "volume": .15},
    Regime.SIDEWAYS:        {"trend": .10, "momentum": .10, "reversion": .65, "volume": .15},
    Regime.HIGH_VOLATILITY: {"trend": .30, "momentum": .25, "reversion": .30, "volume": .15},
}

_VERSIONS = {"1.1": (COMPONENTS_V1_1, WEIGHTS_V1_1), "1.2": (COMPONENTS_V1_2, WEIGHTS_V1_2)}


@dataclass(frozen=True)
class HybridParams:
    version: str = "1.2"

    # Indicator windows
    fast_ema: int = 20
    slow_ema: int = 50
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    momentum_lookback: int = 20
    rsi_window: int = 14
    mr_window: int = 20
    volume_window: int = 20
    atr_period: int = 14
    volratio_window: int = 100

    # Regime thresholds (Section 4.3)
    trend_threshold: float = 0.35
    highvol_threshold: float = 1.5

    # Entry / exit (Sections 8, 12)
    entry_score: float = 0.55
    confirm_score: float = 0.30
    long_exit: float = -0.25
    short_exit: float = 0.25

    # Risk & sizing (Sections 9-11, 13)
    atr_stop_mult: float = 2.0
    risk_budget: float = 0.01
    reward_risk: float = 2.0
    daily_loss_block: float = 0.03
    max_allowed_drawdown: float = 0.20      # was unspecified in v1.1 - now explicit
    max_buying_power_use: float = 0.98      # keep a cash buffer for fees

    # Execution (Section 14)
    execution_threshold: float = 0.01
    adv_window: int = 20                    # was unspecified in v1.1 - now explicit

    # Formula switches (v1.1 = False, v1.2 = True)
    momentum_horizon_scaling: bool = True   # divide by STD(R,20)*sqrt(20)
    mirror_short_confidence: bool = True    # short conviction = 1 - CF

    # Product switch: NSE/BSE cash segment allows shorting intraday only (no overnight).
    allow_short: bool = False

    epsilon: float = 1e-9

    def __post_init__(self):
        if self.version not in _VERSIONS:
            raise ValueError(f"unknown algorithm version {self.version}")

    @property
    def components(self):
        return _VERSIONS[self.version][0]

    @property
    def weights(self):
        return _VERSIONS[self.version][1]

    @property
    def warmup_bars(self) -> int:
        return max(self.slow_ema, self.volratio_window + self.atr_period, self.macd_slow + self.macd_signal) + 1


V1_2 = HybridParams()
V1_1 = replace(V1_2, version="1.1", momentum_horizon_scaling=False, mirror_short_confidence=False)
