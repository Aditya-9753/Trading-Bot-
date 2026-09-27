"""Risk engine (spec Section 9). Runs after a signal, before any order is accepted."""
from dataclasses import dataclass

from ..strategies.params import HybridParams, Side


@dataclass(frozen=True)
class RiskAssessment:
    risk_vol: float
    risk_dd: float
    risk_confidence: float
    risk_score: float


def conviction_factor(confidence_factor: float, side: str, p: HybridParams) -> float:
    """Conviction in the direction being traded.

    v1.1 (spec-literal): CF = (S+1)/2 for both sides -> strong short S=-0.8 gets 0.10 (near-zero size).
    v1.2: shorts use 1-CF, so long S=+0.8 and short S=-0.8 both get 0.90. Symmetric.
    """
    if side == Side.SHORT and p.mirror_short_confidence:
        return 1.0 - confidence_factor
    return confidence_factor


def assess(vol_ratio: float, current_drawdown: float, conviction: float, p: HybridParams) -> RiskAssessment:
    r_vol = min(1.0, max(0.0, vol_ratio) / 2)
    r_dd = min(1.0, max(0.0, current_drawdown) / p.max_allowed_drawdown)
    r_conf = min(1.0, max(0.0, 1.0 - conviction))
    return RiskAssessment(r_vol, r_dd, r_conf, 0.40 * r_vol + 0.35 * r_dd + 0.25 * r_conf)
