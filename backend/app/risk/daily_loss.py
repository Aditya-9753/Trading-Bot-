"""Daily loss block (spec Section 13): -3% of start-of-day equity blocks NEW trades for the session."""
from ..strategies.params import HybridParams


def is_blocked(start_of_day_equity: float, current_equity: float, p: HybridParams) -> bool:
    if start_of_day_equity <= 0:
        return True
    return (current_equity / start_of_day_equity - 1) <= -p.daily_loss_block
