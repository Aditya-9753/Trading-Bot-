"""Orders, trades, portfolio, P&L analytics, risk limits."""
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...models import Account, Bot, EquitySnapshot, Instrument, Order, Position, Trade, User
from ...services import broker
from ...services.events import audit
from ..deps import current_account, current_user, instrument_or_404

router = APIRouter(tags=["trading"])


class OrderIn(BaseModel):
    symbol: str
    side: str = Field(pattern="^(BUY|SELL)$")
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT|STOP)$")
    quantity: int = Field(gt=0, le=1_000_000)
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    target: float | None = Field(default=None, gt=0)


def iso(d: datetime | None):
    return d.isoformat() + "Z" if d else None


def order_out(o: Order, symbol: str) -> dict:
    return {"id": o.id, "symbol": symbol, "side": o.side, "order_type": o.order_type, "quantity": o.quantity,
            "limit_price": o.limit_price, "stop_price": o.stop_price, "stop_loss": o.stop_loss, "target": o.target,
            "status": o.status, "filled_qty": o.filled_qty, "avg_fill_price": o.avg_fill_price, "fees": o.fees,
            "reject_reason": o.reject_reason, "source": o.source, "bot_id": o.bot_id,
            "created_at": iso(o.created_at), "updated_at": iso(o.updated_at)}


@router.post("/orders", status_code=201)
def create_order(body: OrderIn, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    inst = instrument_or_404(db, body.symbol)
    try:
        o = broker.place_order(db, acc.id, inst, body.side, body.order_type, body.quantity, body.limit_price,
                               body.stop_price, body.stop_loss, body.target, source="MANUAL")
    except broker.OrderRejected as e:
        raise HTTPException(400, {"message": e.reason, "order_id": e.order.id if e.order else None})
    return order_out(o, inst.symbol)


@router.get("/orders")
def list_orders(status: str = "", symbol: str = "", source: str = "", limit: int = Query(100, le=500),
                offset: int = 0, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    stmt = select(Order, Instrument.symbol).join(Instrument, Instrument.id == Order.instrument_id) \
        .where(Order.account_id == acc.id)
    if status:
        stmt = stmt.where(Order.status == status.upper())
    if symbol:
        stmt = stmt.where(Instrument.symbol == symbol.upper())
    if source:
        stmt = stmt.where(Order.source == source.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Order.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [order_out(o, s) for o, s in rows]}


@router.get("/orders/{oid}")
def get_order(oid: int, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    o = db.get(Order, oid)
    if o is None or o.account_id != acc.id:
        raise HTTPException(404, "Order not found")
    return order_out(o, db.get(Instrument, o.instrument_id).symbol)


@router.post("/orders/{oid}/cancel")
def cancel(oid: int, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    try:
        o = broker.cancel_order(db, acc.id, oid)
    except broker.OrderRejected as e:
        raise HTTPException(400, e.reason)
    return order_out(o, db.get(Instrument, o.instrument_id).symbol)


@router.get("/trades")
def list_trades(symbol: str = "", limit: int = Query(200, le=1000), offset: int = 0,
                db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    stmt = select(Trade, Instrument.symbol).join(Instrument, Instrument.id == Trade.instrument_id) \
        .where(Trade.account_id == acc.id)
    if symbol:
        stmt = stmt.where(Instrument.symbol == symbol.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Trade.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": t.id, "order_id": t.order_id, "symbol": s, "side": t.side,
                                       "quantity": t.quantity, "price": t.price, "fees": t.fees,
                                       "realized_pnl": t.realized_pnl, "bot_id": t.bot_id,
                                       "created_at": iso(t.created_at)} for t, s in rows]}


# ---- portfolio ---------------------------------------------------------------
def portfolio_summary(db: Session, acc: Account) -> dict:
    db.refresh(acc)
    rows = broker.positions(db, acc.id)
    bot_qty = defaultdict(int)
    for b in db.scalars(select(Bot).where(Bot.user_id == acc.user_id, Bot.position_qty > 0)):
        bot_qty[b.instrument_id] += b.position_qty
    pos_out, invested, mkt = [], 0.0, 0.0
    for p, i in rows:
        value = p.quantity * i.last_price
        cost = p.quantity * p.avg_price
        invested += cost
        mkt += value
        pos_out.append({"symbol": i.symbol, "name": i.name, "quantity": p.quantity, "avg_price": round(p.avg_price, 2),
                        "last_price": i.last_price, "market_value": round(value, 2),
                        "unrealized_pnl": round(value - cost, 2),
                        "unrealized_pct": round((value / cost - 1) * 100, 2) if cost else 0.0,
                        "day_change": round((i.last_price - i.prev_close) * p.quantity, 2),
                        "stop_loss": p.stop_loss, "target": p.target, "bot_quantity": bot_qty.get(i.id, 0),
                        "opened_at": iso(p.opened_at)})
    eq = acc.cash + mkt
    broker.roll_day(acc, eq)
    db.commit()
    return {
        "cash": round(acc.cash, 2), "invested": round(invested, 2), "market_value": round(mkt, 2),
        "equity": round(eq, 2), "starting_cash": acc.starting_cash,
        "total_pnl": round(eq - acc.starting_cash, 2),
        "total_pnl_pct": round((eq / acc.starting_cash - 1) * 100, 2),
        "realized_pnl": round(acc.realized_pnl, 2), "unrealized_pnl": round(mkt - invested, 2),
        "day_pnl": round(eq - acc.day_start_equity, 2),
        "day_pnl_pct": round((eq / acc.day_start_equity - 1) * 100, 2) if acc.day_start_equity else 0.0,
        "fees_paid": round(acc.fees_paid, 2), "trades_today": acc.trades_today,
        "drawdown_pct": round((1 - eq / acc.peak_equity) * 100, 2) if acc.peak_equity else 0.0,
        "positions": sorted(pos_out, key=lambda x: -x["market_value"]),
    }


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    return portfolio_summary(db, acc)


@router.get("/portfolio/equity")
def equity_history(limit: int = Query(500, le=5000), db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    rows = db.scalars(select(EquitySnapshot).where(EquitySnapshot.account_id == acc.id)
                      .order_by(EquitySnapshot.id.desc()).limit(limit)).all()[::-1]
    return [{"t": iso(r.ts), "equity": r.equity, "cash": r.cash} for r in rows]


@router.get("/portfolio/analytics")
def analytics(db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    rows = db.execute(select(Trade, Instrument.symbol).join(Instrument, Instrument.id == Trade.instrument_id)
                      .where(Trade.account_id == acc.id, Trade.side == "SELL")).all()
    pnls = [t.realized_pnl for t, _ in rows]
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
    by_symbol, by_source = defaultdict(float), defaultdict(float)
    for t, s in rows:
        by_symbol[s] += t.realized_pnl
        by_source["BOT" if t.bot_id else "MANUAL"] += t.realized_pnl
    snaps = db.scalars(select(EquitySnapshot.equity).where(EquitySnapshot.account_id == acc.id)
                       .order_by(EquitySnapshot.id)).all()
    peak, max_dd = 0.0, 0.0
    for e in snaps:
        peak = max(peak, e)
        max_dd = min(max_dd, e / peak - 1) if peak else max_dd
    gross_loss = -sum(losses)
    return {
        "closed_trades": len(pnls), "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "largest_win": round(max(wins), 2) if wins else None,
        "largest_loss": round(min(losses), 2) if losses else None,
        "realized_pnl": round(sum(pnls), 2), "fees_paid": round(acc.fees_paid, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "by_symbol": [{"symbol": k, "pnl": round(v, 2)} for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])],
        "by_source": [{"source": k, "pnl": round(v, 2)} for k, v in by_source.items()],
    }


class RiskLimitsIn(BaseModel):
    daily_loss_limit_pct: float = Field(ge=0.005, le=0.20)
    max_position_pct: float = Field(ge=0.01, le=1.0)
    max_open_positions: int = Field(ge=1, le=100)
    max_daily_trades: int = Field(ge=1, le=1000)


def limits_out(acc: Account) -> dict:
    return {"daily_loss_limit_pct": acc.daily_loss_limit_pct, "max_position_pct": acc.max_position_pct,
            "max_open_positions": acc.max_open_positions, "max_daily_trades": acc.max_daily_trades,
            "short_selling": False}


@router.get("/portfolio/risk-limits")
def get_limits(acc: Account = Depends(current_account)):
    return limits_out(acc)


@router.put("/portfolio/risk-limits")
def put_limits(body: RiskLimitsIn, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    with broker.account_lock(acc.id):
        a = broker.lock_account(db, acc.id)
        for k, v in body.model_dump().items():
            setattr(a, k, v)
        audit(db, a.user_id, "portfolio.risk_limits", "", body.model_dump())
        db.commit()
        return limits_out(a)


class ProtectIn(BaseModel):
    stop_loss: float | None = Field(default=None, gt=0)
    target: float | None = Field(default=None, gt=0)


@router.patch("/portfolio/positions/{symbol}")
def set_protection(symbol: str, body: ProtectIn, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    inst = instrument_or_404(db, symbol)
    with broker.account_lock(acc.id):
        broker.lock_account(db, acc.id)
        pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == inst.id))
        if pos is None or pos.quantity <= 0:
            raise HTTPException(404, "You don't hold this stock")
        if body.stop_loss is not None and body.stop_loss >= inst.last_price:
            raise HTTPException(400, "Stop-loss must be below the current price")
        if body.target is not None and body.target <= inst.last_price:
            raise HTTPException(400, "Target must be above the current price")
        pos.stop_loss, pos.target = body.stop_loss, body.target
        db.commit()
    return {"ok": True, "symbol": inst.symbol, "stop_loss": pos.stop_loss, "target": pos.target}


class ResetIn(BaseModel):
    confirm: bool


@router.post("/portfolio/reset")
def reset(body: ResetIn, db: Session = Depends(get_db), acc: Account = Depends(current_account)):
    if not body.confirm:
        raise HTTPException(400, "Set confirm=true to reset your practice account")
    broker.reset_account(db, acc.id, settings.STARTING_CASH)
    audit(db, acc.user_id, "portfolio.reset", "")
    db.commit()
    return {"ok": True}
