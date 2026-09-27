"""Stop loss / take profit / trailing stop (spec Section 11)."""
from dataclasses import dataclass

from ..strategies.params import HybridParams, Side


@dataclass(frozen=True)
class Levels:
    stop_loss: float
    take_profit: float
    risk_unit: float


def initial_levels(side: str, entry: float, atr: float, p: HybridParams) -> Levels:
    d = p.atr_stop_mult * atr
    if side == Side.LONG:
        sl = entry - d
        return Levels(sl, entry + p.reward_risk * (entry - sl), entry - sl)
    sl = entry + d
    return Levels(sl, entry - p.reward_risk * (sl - entry), sl - entry)


def trailing_stop(side: str, extreme_since_entry: float, atr: float, p: HybridParams) -> float:
    d = p.atr_stop_mult * atr
    return extreme_since_entry - d if side == Side.LONG else extreme_since_entry + d


def tighten(side: str, current_stop: float, candidate: float) -> float:
    """Stops only ever move in the position's favour."""
    if candidate != candidate:
        return current_stop
    return max(current_stop, candidate) if side == Side.LONG else min(current_stop, candidate)
