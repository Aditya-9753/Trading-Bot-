"""Position sizing (spec Section 10)."""
import math
from dataclasses import dataclass

from ..strategies.params import HybridParams


@dataclass(frozen=True)
class SizeResult:
    sl_distance: float
    base_size: float
    final_size: float
    quantity: int
    capped_by_cash: bool


def size(capital: float, atr: float, conviction: float, risk_score: float, p: HybridParams,
         price: float | None = None, buying_power: float | None = None) -> SizeResult:
    sl_distance = p.atr_stop_mult * atr
    if not (sl_distance > 0) or capital <= 0:
        return SizeResult(sl_distance, 0.0, 0.0, 0, False)
    base = capital * p.risk_budget / sl_distance
    final = max(0.0, base * conviction * (1 - risk_score))
    capped = False
    if price and buying_power is not None and final * price > buying_power:
        final, capped = max(0.0, buying_power / price), True
    return SizeResult(sl_distance, base, final, int(math.floor(final)), capped)
