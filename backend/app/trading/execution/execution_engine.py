"""Execution routing + cost model (spec Section 14, PRD Section 16).

Cost defaults approximate Indian equity DELIVERY charges with zero brokerage (paper).
They are assumptions - verify current STT / stamp duty / exchange rates before relying on them.
"""
from dataclasses import dataclass

from ...strategies.params import HybridParams

NORMAL, VWAP, TWAP = "NORMAL", "VWAP", "TWAP"


def route(quantity: int, price: float, adv_value: float, p: HybridParams, has_intraday_profile: bool = False):
    """Returns (policy, order_ratio). Split orders use VWAP if a volume profile exists, else TWAP."""
    if not adv_value or adv_value != adv_value:
        return NORMAL, float("nan")
    ratio = quantity * price / adv_value
    if ratio > p.execution_threshold:
        return (VWAP if has_intraday_profile else TWAP), ratio
    return NORMAL, ratio


@dataclass(frozen=True)
class CostModel:
    brokerage_pct: float = 0.0
    stt_pct: float = 0.001              # delivery: both buy and sell
    exchange_txn_pct: float = 0.0000297
    sebi_pct: float = 0.000001
    stamp_buy_pct: float = 0.00015
    gst_pct: float = 0.18               # on brokerage + exchange + SEBI
    slippage_bps: float = 5.0
    half_spread_bps: float = 2.0
    impact_bps_per_pct_adv: float = 10.0  # extra slippage for split orders (ASSUMPTION)

    def fees(self, is_buy: bool, value: float) -> float:
        taxable = value * (self.brokerage_pct + self.exchange_txn_pct + self.sebi_pct)
        f = value * self.stt_pct + taxable * (1 + self.gst_pct)
        if is_buy:
            f += value * self.stamp_buy_pct
        return f

    def fill_price(self, is_buy: bool, ref_price: float, policy: str = NORMAL, ratio: float = 0.0) -> float:
        bps = self.slippage_bps + self.half_spread_bps
        if policy != NORMAL and ratio == ratio:
            bps += self.impact_bps_per_pct_adv * ratio * 100
        adj = bps / 10_000
        return ref_price * (1 + adj) if is_buy else ref_price * (1 - adj)
