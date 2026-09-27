"""Single-bar evaluation used by live paper bots (same math as the backtester)."""
from ..params import HybridParams, Side, V1_2
from ..built_in.hybrid_strategy import compute_features
from .signal_engine import entry_signal, component_contributions


def evaluate(df, p: HybridParams = V1_2, position_side: str | None = None) -> dict:
    """Evaluate the latest CLOSED candle. Returns a JSON-serialisable decision for bot logs / UI."""
    f = compute_features(df, p)
    last, prev = f.iloc[-1], f.iloc[-2] if len(f) > 1 else None
    s, s_prev = float(last["S"]), float(prev["S"]) if prev is not None else float("nan")

    if position_side == Side.LONG:
        action = "EXIT" if s < p.long_exit else "HOLD"
    elif position_side == Side.SHORT:
        action = "EXIT" if s > p.short_exit else "HOLD"
    else:
        action = entry_signal(s, s_prev, last["regime"], p)
        if action == "SELL" and not p.allow_short:
            action = "HOLD"

    contrib = component_contributions(f.iloc[[-1]], p).iloc[0]
    return {
        "algorithm_version": p.version,
        "time": str(f.index[-1]),
        "regime": last["regime"],
        "S": s,
        "confidence": float(last["confidence"]),
        "atr": float(last["atr"]),
        "vol_ratio": float(last["vol_ratio"]),
        "contributions": {k: float(v) for k, v in contrib.items()},
        "action": action,
    }
