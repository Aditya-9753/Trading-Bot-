"""Back-adjust history for a split or bonus so indicators and backtests see a continuous series.

  python -m scripts.corporate_actions RELIANCE --ex-date 2024-10-28 --bonus 1:1
  python -m scripts.corporate_actions INFY --ex-date 2025-01-10 --split 10:2      (face value 10 -> 2)

factor = new shares per old share (bonus 1:1 -> 2.0, split 10:2 -> 5.0).
Candles BEFORE the ex-date: prices / factor, volume * factor. Paper positions are converted too
(quantity * factor, average price / factor) and OPEN orders on the symbol are cancelled.
Cash dividends are not adjusted (common practice for price charts; returns differ slightly).
Applying the same event twice would double-adjust: every run is written to the audit log.
"""
import argparse
import math
import sys
from datetime import date, datetime

from sqlalchemy import select, update


def factor_from(split: str | None, bonus: str | None) -> float:
    if bool(split) == bool(bonus):
        raise ValueError("give exactly one of --split OLD_FV:NEW_FV or --bonus NEW:HELD")
    a, b = (float(x) for x in (split or bonus).split(":"))
    if a <= 0 or b <= 0:
        raise ValueError("ratio parts must be positive")
    return a / b if split else (a + b) / b


def apply(db, symbol: str, ex_date: date, factor: float) -> dict:
    from app.models import Candle, Instrument, Order, Position
    from app.services.events import audit
    from app.services.market_data import refresh_last_price
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if inst is None:
        raise ValueError(f"unknown symbol {symbol}")
    cutoff = datetime.combine(ex_date, datetime.min.time())
    n = db.execute(update(Candle).where(Candle.instrument_id == inst.id, Candle.ts < cutoff).values(
        open=Candle.open / factor, high=Candle.high / factor, low=Candle.low / factor,
        close=Candle.close / factor, volume=Candle.volume * factor)).rowcount
    moved = 0
    for p in db.scalars(select(Position).where(Position.instrument_id == inst.id, Position.quantity > 0)):
        p.quantity = int(math.floor(p.quantity * factor))
        p.avg_price /= factor
        p.stop_loss = p.stop_loss / factor if p.stop_loss else None
        p.target = p.target / factor if p.target else None
        moved += 1
    cancelled = db.execute(update(Order).where(Order.instrument_id == inst.id, Order.status == "OPEN")
                           .values(status="CANCELLED", reject_reason="Corporate action adjustment")).rowcount
    refresh_last_price(db, inst)
    audit(db, None, "data.corporate_action", inst.symbol,
          {"ex_date": ex_date.isoformat(), "factor": factor, "candles": n, "positions": moved, "orders_cancelled": cancelled})
    db.commit()
    return {"candles": n, "positions": moved, "orders_cancelled": cancelled}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol")
    ap.add_argument("--ex-date", required=True, type=date.fromisoformat)
    ap.add_argument("--split")
    ap.add_argument("--bonus")
    a = ap.parse_args(argv)
    f = factor_from(a.split, a.bonus)
    from app.core.db import SessionLocal
    with SessionLocal() as db:
        r = apply(db, a.symbol, a.ex_date, f)
    print(f"{a.symbol}: factor {f:g}; adjusted {r['candles']} candles, {r['positions']} positions, "
          f"cancelled {r['orders_cancelled']} open orders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
