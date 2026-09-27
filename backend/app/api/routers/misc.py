"""Alerts, notifications, dashboard, admin, WebSocket."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import SessionLocal, get_db
from ...models import (Account, Alert, AuditLog, Backtest, Bot, BotStatus, Instrument, Notification, Order, Role,
                       Trade, User, Watchlist, utcnow)
from ...services import bots as bot_svc
from ...services import broker
from ...services.events import audit, notify
from ...services.market_data import get_setting, set_setting, trading_halted
from ...services.realtime import hub
from ..deps import (client_ip, current_account, current_user, instrument_or_404, require_admin, require_super_admin,
                    user_from_token)
from .markets import inst_out
from .strategy import bot_out
from .trading import iso, order_out, portfolio_summary

router = APIRouter()


# ---- alerts ------------------------------------------------------------------
class AlertIn(BaseModel):
    symbol: str
    condition: str = Field(pattern="^(ABOVE|BELOW)$")
    price: float = Field(gt=0)
    note: str = Field(default="", max_length=200)


def alert_out(a: Alert, symbol: str, last: float) -> dict:
    return {"id": a.id, "symbol": symbol, "condition": a.condition, "price": a.price, "note": a.note,
            "is_active": a.is_active, "triggered_at": iso(a.triggered_at), "created_at": iso(a.created_at),
            "last_price": last}


@router.get("/alerts", tags=["alerts"])
def list_alerts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(Alert, Instrument).join(Instrument, Instrument.id == Alert.instrument_id)
                      .where(Alert.user_id == user.id).order_by(Alert.is_active.desc(), Alert.id.desc())).all()
    return [alert_out(a, i.symbol, i.last_price) for a, i in rows]


@router.post("/alerts", status_code=201, tags=["alerts"])
def create_alert(body: AlertIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inst = instrument_or_404(db, body.symbol)
    if db.scalar(select(func.count(Alert.id)).where(Alert.user_id == user.id, Alert.is_active == True)) >= 50:  # noqa: E712
        raise HTTPException(400, "At most 50 active alerts")
    if body.condition == "ABOVE" and body.price <= inst.last_price:
        raise HTTPException(400, f"Price is already above ₹{body.price:,.2f} (now ₹{inst.last_price:,.2f})")
    if body.condition == "BELOW" and body.price >= inst.last_price:
        raise HTTPException(400, f"Price is already below ₹{body.price:,.2f} (now ₹{inst.last_price:,.2f})")
    a = Alert(user_id=user.id, instrument_id=inst.id, condition=body.condition, price=body.price, note=body.note)
    db.add(a)
    db.commit()
    return alert_out(a, inst.symbol, inst.last_price)


@router.delete("/alerts/{aid}", tags=["alerts"])
def delete_alert(aid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a = db.get(Alert, aid)
    if a is None or a.user_id != user.id:
        raise HTTPException(404, "Alert not found")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.get("/notifications", tags=["alerts"])
def list_notifications(unread_only: bool = False, limit: int = Query(50, le=200), db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    rows = db.scalars(stmt.order_by(Notification.id.desc()).limit(limit)).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                                 Notification.is_read == False))  # noqa: E712
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
                                         "is_read": n.is_read, "created_at": iso(n.created_at)} for n in rows]}


@router.post("/notifications/{nid}/read", tags=["alerts"])
def read_notification(nid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all", tags=["alerts"])
def read_all(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False) \
        .update({Notification.is_read: True})  # noqa: E712
    db.commit()
    return {"ok": True}


# ---- dashboard -----------------------------------------------------------------
@router.get("/dashboard", tags=["dashboard"])
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user), acc: Account = Depends(current_account)):
    pf = portfolio_summary(db, acc)
    recent = db.execute(select(Order, Instrument.symbol).join(Instrument, Instrument.id == Order.instrument_id)
                        .where(Order.account_id == acc.id).order_by(Order.id.desc()).limit(8)).all()
    bots = db.scalars(select(Bot).where(Bot.user_id == user.id).order_by(Bot.id.desc())).all()
    movers = sorted((inst_out(i) for i in db.scalars(select(Instrument).where(Instrument.is_active == True))),  # noqa: E712
                    key=lambda x: -abs(x["change_pct"]))[:6]
    checklist = [
        {"key": "watchlist", "label": "Create a watchlist", "done": bool(db.scalar(select(func.count(Watchlist.id)).where(Watchlist.user_id == user.id)))},
        {"key": "order", "label": "Place your first practice order", "done": bool(db.scalar(select(func.count(Trade.id)).where(Trade.account_id == acc.id)))},
        {"key": "backtest", "label": "Run a backtest", "done": bool(db.scalar(select(func.count(Backtest.id)).where(Backtest.user_id == user.id)))},
        {"key": "bot", "label": "Start a bot", "done": any(b.status in (BotStatus.RUNNING, BotStatus.PAUSED) or b.trade_count for b in bots)},
        {"key": "alert", "label": "Set a price alert", "done": bool(db.scalar(select(func.count(Alert.id)).where(Alert.user_id == user.id)))},
    ]
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read == False))  # noqa: E712
    return {"portfolio": {k: v for k, v in pf.items() if k != "positions"}, "positions": pf["positions"][:6],
            "recent_orders": [order_out(o, s) for o, s in recent],
            "bots": {"total": len(bots), "running": sum(b.status == BotStatus.RUNNING for b in bots),
                     "error": sum(b.status == BotStatus.ERROR for b in bots),
                     "items": [bot_out(db, b) for b in bots[:4]]},
            "movers": movers, "checklist": checklist, "unread_notifications": unread,
            "kill_switch": trading_halted(db), "simulated": True}


# ---- admin -----------------------------------------------------------------------
class UserPatch(BaseModel):

    is_active: bool | None = None
    role: str | None = None


@router.get("/admin/stats", tags=["admin"])
def admin_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    since = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return {"users": db.scalar(select(func.count(User.id))),
            "active_users": db.scalar(select(func.count(User.id)).where(User.is_active == True)),  # noqa: E712
            "bots_running": db.scalar(select(func.count(Bot.id)).where(Bot.status == BotStatus.RUNNING)),
            "bots_error": db.scalar(select(func.count(Bot.id)).where(Bot.status == BotStatus.ERROR)),
            "orders_today": db.scalar(select(func.count(Order.id)).where(Order.created_at >= since)),
            "trades_today": db.scalar(select(func.count(Trade.id)).where(Trade.created_at >= since)),
            "open_orders": db.scalar(select(func.count(Order.id)).where(Order.status == "OPEN")),
            "instruments": db.scalar(select(func.count(Instrument.id))),
            "kill_switch": get_setting(db, "kill_switch", {"active": False})}


@router.get("/admin/users", tags=["admin"])
def admin_users(q: str = "", limit: int = Query(100, le=500), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(User, Account).join(Account, Account.user_id == User.id, isouter=True)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(User.id).limit(limit)).all()
    out = []
    for u, a in rows:
        out.append({"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
                    "created_at": iso(u.created_at), "last_login_at": iso(u.last_login_at),
                    "equity": round(broker.equity(db, a), 2) if a else None,
                    "bots": db.scalar(select(func.count(Bot.id)).where(Bot.user_id == u.id))})
    return out


@router.patch("/admin/users/{uid}", tags=["admin"])
def admin_update_user(uid: int, body: UserPatch, request: Request, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot change your own role or status")
    if u.role == Role.SUPER_ADMIN and admin.role != Role.SUPER_ADMIN:
        raise HTTPException(403, "Only a super-admin can change a super-admin")
    if body.role is not None:
        if body.role not in Role.ALL:
            raise HTTPException(422, "Invalid role")
        if admin.role != Role.SUPER_ADMIN:
            raise HTTPException(403, "Only a super-admin can change roles")
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
        if not body.is_active:  # disabling a user stops their bots
            for b in db.scalars(select(Bot).where(Bot.user_id == u.id, Bot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))):
                bot_svc.stop_bot(db, b)
    audit(db, admin.id, "admin.update_user", f"user:{u.id}", body.model_dump(exclude_none=True), client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/admin/bots", tags=["admin"])
def admin_bots(status: str = "", db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(Bot, User.email).join(User, User.id == Bot.user_id)
    if status:
        stmt = stmt.where(Bot.status == status.upper())
    return [{**bot_out(db, b), "owner": e} for b, e in db.execute(stmt.order_by(Bot.id.desc()).limit(300)).all()]


@router.get("/admin/audit", tags=["admin"])
def admin_audit(action: str = "", limit: int = Query(200, le=1000), db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    stmt = select(AuditLog, User.email).join(User, User.id == AuditLog.user_id, isouter=True)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    return [{"id": a.id, "user": e, "action": a.action, "target": a.target, "detail": a.detail, "ip": a.ip,
             "created_at": iso(a.created_at)} for a, e in db.execute(stmt.order_by(AuditLog.id.desc()).limit(limit)).all()]


class KillIn(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=300)


@router.get("/admin/kill-switch", tags=["admin"])
def get_kill(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return get_setting(db, "kill_switch", {"active": False})


@router.post("/admin/kill-switch", tags=["admin"])
def set_kill(body: KillIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_super_admin)):
    """Platform kill switch: stops ALL bots, cancels ALL open orders, blocks new buys. Exits stay allowed."""
    stopped = cancelled = 0
    if body.active:
        for b in db.scalars(select(Bot).where(Bot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))).all():
            bot_svc.stop_bot(db, b)
            notify(db, b.user_id, "KILL_SWITCH", f"Bot '{b.name}' stopped by platform kill switch", body.reason)
            stopped += 1
        for o in db.scalars(select(Order).where(Order.status == "OPEN")).all():
            o.status, o.reject_reason = "CANCELLED", "Platform kill switch"
            cancelled += 1
    state = {"active": body.active, "reason": body.reason, "by": admin.email, "at": utcnow().isoformat() + "Z"}
    set_setting(db, "kill_switch", state)
    audit(db, admin.id, "admin.kill_switch", "platform",
          {**state, "bots_stopped": stopped, "orders_cancelled": cancelled}, client_ip(request))
    db.commit()
    hub.publish({"type": "kill_switch", "data": state})
    return {**state, "bots_stopped": stopped, "orders_cancelled": cancelled}


@router.post("/admin/instruments/{symbol}/toggle", tags=["admin"])
def toggle_instrument(symbol: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    inst = instrument_or_404(db, symbol)
    inst.is_active = not inst.is_active
    audit(db, admin.id, "admin.toggle_instrument", inst.symbol, {"is_active": inst.is_active}, client_ip(request))
    db.commit()
    return inst_out(inst)


@router.get("/admin/instruments", tags=["admin"])
def admin_instruments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """All instruments with active/inactive status — admin can toggle them."""
    return [inst_out(i) for i in db.scalars(select(Instrument).order_by(Instrument.symbol)).all()]


class TopUpIn(BaseModel):
    amount: float = Field(ne=0, ge=-10_000_000, le=10_000_000,
                          description="Positive to add cash, negative to deduct")
    note: str = Field(default="", max_length=200)


@router.post("/admin/users/{uid}/topup", tags=["admin"])
def admin_topup(uid: int, body: TopUpIn, request: Request, db: Session = Depends(get_db),
               admin: User = Depends(require_admin)):
    """Add or remove virtual cash from any user's account. The change is logged in the audit trail."""
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(404, "User not found")
    acc = db.scalar(select(Account).where(Account.user_id == uid))
    if acc is None:
        raise HTTPException(404, "User has no account")
    if acc.cash + body.amount < 0:
        raise HTTPException(400, f"Cannot reduce cash below zero (current: ₹{acc.cash:,.2f})")
    acc.cash += body.amount
    audit(db, admin.id, "admin.topup", f"user:{uid}",
          {"amount": body.amount, "note": body.note, "new_cash": round(acc.cash, 2)}, client_ip(request))
    notify(db, uid, "ADMIN_TOPUP",
           f"Your cash was {'increased' if body.amount > 0 else 'decreased'} by ₹{abs(body.amount):,.2f} by an admin",
           body.note or "Virtual practice account adjustment.")
    db.commit()
    return {"ok": True, "new_cash": round(acc.cash, 2), "user_id": uid}


class BroadcastIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(default="", max_length=500)
    kind: str = Field(default="INFO", pattern="^(INFO|WARN|ERROR)$")


@router.post("/admin/broadcast", tags=["admin"])
def admin_broadcast(body: BroadcastIn, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    """Send a platform-wide notification to every active user. Useful for maintenance, updates, etc."""
    users = db.scalars(select(User).where(User.is_active == True)).all()  # noqa: E712
    for u in users:
        notify(db, u.id, f"ADMIN_{body.kind}", body.title, body.body)
    audit(db, admin.id, "admin.broadcast", "platform", {"title": body.title, "recipients": len(users)}, client_ip(request))
    db.commit()
    hub.publish({"type": "notification", "data": {"kind": f"ADMIN_{body.kind}", "title": body.title, "body": body.body}})
    return {"ok": True, "recipients": len(users)}


# ---- websocket -------------------------------------------------------------------
@router.websocket("/ws")
async def ws(websocket: WebSocket, token: str = ""):
    with SessionLocal() as db:
        user = user_from_token(db, token)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    q = hub.subscribe(user.id)
    await websocket.send_json({"type": "hello", "simulated": True})

    async def reader():
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})

    task = asyncio.create_task(reader())
    try:
        while not task.done():
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20)
            except asyncio.TimeoutError:
                msg = {"type": "keepalive"}
            await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        task.cancel()
        hub.unsubscribe(q)
