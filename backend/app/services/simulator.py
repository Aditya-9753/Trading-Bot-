"""Practice-market price simulator.

Every TICK_SECONDS each active instrument gets a new price (geometric random walk with a slowly
changing drift, per-tick volatility derived from the instrument's own history). Every TICKS_PER_BAR
ticks the practice bar closes and is stored as a candle: one practice bar = one compressed session.
On every tick: open orders are matched, stop/target exits and price alerts are checked.
On every bar close: running bots are evaluated and equity snapshots are taken.
ALL prices produced here are SIMULATED and labelled as such in the API and UI.
"""
import asyncio
import logging
import math

import numpy as np
from sqlalchemy import select

from ..core.config import settings
from ..core.db import SessionLocal
from ..models import Alert, Candle, Instrument, utcnow
from . import bots, broker
from .events import notify
from .realtime import hub

log = logging.getLogger(__name__)


def round_tick(p: float, tick: float = 0.05) -> float:
    return round(round(p / tick) * tick, 2)


class Simulator:
    def __init__(self, seed: int | None = None):
        self.rng = np.random.default_rng(seed)
        self.state: dict[int, dict] = {}
        self.running = False
        self.tick_no = 0

    def _init_state(self, db, inst: Instrument) -> dict:
        is_crypto = getattr(inst, "asset_type", "") == "CRYPTO"
        closes = db.scalars(select(Candle.close).where(Candle.instrument_id == inst.id)
                            .order_by(Candle.ts.desc()).limit(120)).all()
        r = np.diff(np.log(np.array(closes[::-1]))) if len(closes) > 2 else np.array([0.035 if is_crypto else 0.015])
        max_vol = 0.08 if is_crypto else 0.04
        daily_vol = float(np.clip(np.std(r) if len(r) > 1 else (0.035 if is_crypto else 0.015), 0.006, max_vol))
        return {"vol": daily_vol, "drift": 0.0, "bar": None, "ticks": 0, "is_crypto": is_crypto}

    def step(self):
        self.tick_no += 1
        n = settings.TICKS_PER_BAR
        with SessionLocal() as db:
            insts = db.scalars(select(Instrument).where(Instrument.is_active == True)).all()  # noqa: E712
            ticks, closed = [], []
            for inst in insts:
                st = self.state.get(inst.id) or self.state.setdefault(inst.id, self._init_state(db, inst))
                if self.rng.random() < 1 / (n * 8):  # drift regime changes every ~8 bars on average
                    st["drift"] = float(self.rng.choice([-1.0, 0.0, 0.0, 1.0])) * st["vol"] * 0.12
                sig = st["vol"] / math.sqrt(n)
                last = inst.last_price
                price = max(0.05, round_tick(last * math.exp(st["drift"] / n + sig * self.rng.standard_normal())))
                vol_base = 5e4 if st.get("is_crypto") else 2e5
                vol = float(max(1, self.rng.lognormal(math.log(vol_base / n), 0.5)))
                b = st["bar"]
                if b is None:
                    st["bar"] = b = {"o": last, "h": max(last, price), "l": min(last, price), "c": price, "v": 0.0}
                b["h"], b["l"], b["c"], b["v"] = max(b["h"], price), min(b["l"], price), price, b["v"] + vol
                st["ticks"] += 1
                inst.last_price, inst.updated_at = price, utcnow()
                ch = price - inst.prev_close
                ticks.append({"symbol": inst.symbol, "price": price, "change": round(ch, 2),
                              "change_pct": round(ch / inst.prev_close * 100, 2) if inst.prev_close else 0.0})
                if st["ticks"] >= n:
                    db.add(Candle(instrument_id=inst.id, ts=utcnow(), open=b["o"], high=b["h"], low=b["l"],
                                  close=b["c"], volume=round(b["v"]), source="SIMULATED"))
                    inst.prev_close = b["c"]
                    closed.append(inst.id)
                    st["bar"], st["ticks"] = None, 0
            db.commit()
            hub.publish({"type": "ticks", "simulated": True, "data": ticks})

            for inst in insts:
                self._after_tick(db, inst)
            for iid in closed:
                inst = db.get(Instrument, iid)
                hub.publish({"type": "bar", "data": {"symbol": inst.symbol, "close": inst.last_price}})
                try:
                    bots.on_bar_close(db, inst)
                except Exception:
                    db.rollback()
                    log.exception("bar-close processing failed for %s", inst.symbol)
            if closed:
                broker.snapshot_equity(db)

    def _after_tick(self, db, inst: Instrument):
        price = inst.last_price
        try:
            broker.match_open_orders(db, inst, price)
            broker.check_protective_exits(db, inst, price)
            bots.on_tick(db, inst, price)
            check_alerts(db, inst, price)
        except Exception:
            db.rollback()
            log.exception("tick processing failed for %s", inst.symbol)

    async def run(self):
        self.running = True
        log.info("practice-market simulator started (tick=%ss, %s ticks/bar)", settings.TICK_SECONDS, settings.TICKS_PER_BAR)
        while self.running:
            try:
                await asyncio.to_thread(self.step)
            except Exception:
                log.exception("simulator step failed")
            await asyncio.sleep(settings.TICK_SECONDS)

    def stop(self):
        self.running = False


def check_alerts(db, inst: Instrument, price: float) -> int:
    alerts = db.scalars(select(Alert).where(Alert.instrument_id == inst.id, Alert.is_active == True)).all()  # noqa: E712
    n = 0
    for a in alerts:
        if (a.condition == "ABOVE" and price >= a.price) or (a.condition == "BELOW" and price <= a.price):
            a.is_active, a.triggered_at = False, utcnow()
            word = "rose above" if a.condition == "ABOVE" else "fell below"
            notify(db, a.user_id, "PRICE_ALERT", f"{inst.symbol} {word} ₹{a.price:,.2f}",
                   f"Price now ₹{price:,.2f}. {a.note}".strip())
            n += 1
    if n:
        db.commit()
    return n


simulator = Simulator()
