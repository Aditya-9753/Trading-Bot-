from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...bots.market_calendar import ExchangeCalendar
from ...core.config import settings
from ...core.db import get_db
from ...models import Instrument, User, Watchlist, WatchlistItem, utcnow
from ...services.market_data import chart_payload, load_df, trading_halted
from ..deps import current_user, instrument_or_404

router = APIRouter(tags=["markets"])
NSE = ExchangeCalendar()


def inst_out(i: Instrument) -> dict:
    ch = i.last_price - i.prev_close
    return {"symbol": i.symbol, "name": i.name, "exchange": i.exchange, "series": i.series or "EQ",
            "sector": i.sector, "asset_type": getattr(i, "asset_type", "EQUITY") or "EQUITY",
            "last_price": i.last_price, "prev_close": i.prev_close, "change": round(ch, 2),
            "change_pct": round(ch / i.prev_close * 100, 2) if i.prev_close else 0.0,
            "data_source": i.data_source, "simulated": True, "is_active": i.is_active,
            "updated_at": i.updated_at.isoformat() + "Z"}


@router.get("/markets/status")
def market_status(db: Session = Depends(get_db)):
    from datetime import timezone
    now = utcnow().replace(tzinfo=timezone.utc)
    return {"practice_market_open": settings.ENABLE_SIMULATOR and not trading_halted(db),
            "nse_session_open": NSE.is_open(now), "simulated": True, "kill_switch": trading_halted(db),
            "ticks_per_bar": settings.TICKS_PER_BAR, "tick_seconds": settings.TICK_SECONDS,
            "note": "Practice market: prices are SIMULATED and run 24x7. One practice bar = one compressed session."}


@router.get("/markets")
def list_markets(q: str = "", sector: str = "", asset_type: str = "", db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(Instrument).order_by(Instrument.symbol)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Instrument.symbol.ilike(like), Instrument.name.ilike(like)))
    if sector:
        stmt = stmt.where(Instrument.sector == sector)
    if asset_type:
        stmt = stmt.where(Instrument.asset_type == asset_type.upper())
    return [inst_out(i) for i in db.scalars(stmt).all()]


@router.get("/markets/{symbol}")
def get_market(symbol: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    inst = instrument_or_404(db, symbol)
    df = load_df(db, inst.id, limit=260)
    out = inst_out(inst)
    if len(df):
        out.update({"high_52w": round(float(df["high"].max()), 2), "low_52w": round(float(df["low"].min()), 2),
                    "avg_volume_20": round(float(df["volume"].tail(20).mean()))})
    return out


@router.get("/markets/{symbol}/candles")
def candles(symbol: str, bars: int = Query(250, ge=20, le=2000), db: Session = Depends(get_db),
            _: User = Depends(current_user)):
    inst = instrument_or_404(db, symbol)
    df = load_df(db, inst.id, limit=bars + 120)
    return {"symbol": inst.symbol, "simulated": True, **chart_payload(df, bars)}


# ---- watchlists ------------------------------------------------------------
class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class ItemIn(BaseModel):
    symbol: str


def wl_out(db: Session, w: Watchlist) -> dict:
    ids = [it.instrument_id for it in w.items]
    insts = db.scalars(select(Instrument).where(Instrument.id.in_(ids))).all() if ids else []
    return {"id": w.id, "name": w.name, "items": [inst_out(i) for i in sorted(insts, key=lambda i: i.symbol)]}


def _own_wl(db: Session, wid: int, user: User) -> Watchlist:
    w = db.get(Watchlist, wid)
    if w is None or w.user_id != user.id:
        raise HTTPException(404, "Watchlist not found")
    return w


@router.get("/watchlists")
def list_watchlists(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [wl_out(db, w) for w in db.scalars(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.id))]


@router.post("/watchlists", status_code=201)
def create_watchlist(body: WatchlistIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if len(db.scalars(select(Watchlist.id).where(Watchlist.user_id == user.id)).all()) >= 10:
        raise HTTPException(400, "You can have at most 10 watchlists")
    w = Watchlist(user_id=user.id, name=body.name.strip())
    db.add(w)
    db.commit()
    return wl_out(db, w)


@router.patch("/watchlists/{wid}")
def rename_watchlist(wid: int, body: WatchlistIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = _own_wl(db, wid, user)
    w.name = body.name.strip()
    db.commit()
    return wl_out(db, w)


@router.delete("/watchlists/{wid}")
def delete_watchlist(wid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(_own_wl(db, wid, user))
    db.commit()
    return {"ok": True}


@router.post("/watchlists/{wid}/items", status_code=201)
def add_item(wid: int, body: ItemIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = _own_wl(db, wid, user)
    inst = instrument_or_404(db, body.symbol)
    if any(it.instrument_id == inst.id for it in w.items):
        raise HTTPException(409, f"{inst.symbol} is already in this watchlist")
    if len(w.items) >= 50:
        raise HTTPException(400, "A watchlist can hold at most 50 stocks")
    w.items.append(WatchlistItem(instrument_id=inst.id))
    db.commit()
    db.refresh(w)
    return wl_out(db, w)


@router.delete("/watchlists/{wid}/items/{symbol}")
def remove_item(wid: int, symbol: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = _own_wl(db, wid, user)
    inst = instrument_or_404(db, symbol)
    for it in list(w.items):
        if it.instrument_id == inst.id:
            w.items.remove(it)
    db.commit()
    db.refresh(w)
    return wl_out(db, w)
