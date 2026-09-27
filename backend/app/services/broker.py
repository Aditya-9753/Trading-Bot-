"""Paper broker: pre-trade risk checks, fills, open-order matching, protective exits.

Concurrency: every state change of an account happens while holding
  (1) a row lock on the account  (SELECT ... FOR UPDATE on MySQL/Postgres), and
  (2) an in-process per-account lock (SQLite ignores FOR UPDATE; also serialises threads).
so a manual order and a bot order arriving together can never overdraw cash or oversell a position.

Rules:
  * Cash (delivery) segment, long-only: no short selling. SELL qty <= held qty - qty reserved by open sells.
  * Exposure limits (daily loss, position size %, max open positions, daily trade count, kill switch)
    apply ONLY to new BUY orders, so a stop-loss or exit can never be blocked.
  * Fills use the engine's CostModel (slippage + STT, stamp duty, exchange, SEBI, GST).
"""
import logging
import threading
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Account, EquitySnapshot, Instrument, Order, Position, Trade, User, utcnow
from ..trading.execution.execution_engine import CostModel
from .events import notify
from .market_data import trading_halted
from .realtime import hub

log = logging.getLogger(__name__)
COSTS = CostModel()
_locks: dict[int, threading.RLock] = defaultdict(threading.RLock)
_locks_guard = threading.Lock()

BUY, SELL = "BUY", "SELL"
MARKET, LIMIT, STOP = "MARKET", "LIMIT", "STOP"
OPEN, FILLED, CANCELLED, REJECTED = "OPEN", "FILLED", "CANCELLED", "REJECTED"


class OrderRejected(Exception):
    def __init__(self, reason: str, order: Order | None = None):
        super().__init__(reason)
        self.reason, self.order = reason, order


def account_lock(account_id: int) -> threading.RLock:
    with _locks_guard:
        return _locks[account_id]


def lock_account(db: Session, account_id: int) -> Account:
    acc = db.execute(select(Account).where(Account.id == account_id)
                     .with_for_update().execution_options(populate_existing=True)).scalar_one()
    return acc


def positions(db: Session, account_id: int) -> list[tuple[Position, Instrument]]:
    return db.execute(select(Position, Instrument).join(Instrument, Instrument.id == Position.instrument_id)
                      .where(Position.account_id == account_id, Position.quantity > 0)
                      .execution_options(populate_existing=True)).all()


def equity(db: Session, acc: Account) -> float:
    return acc.cash + sum(p.quantity * i.last_price for p, i in positions(db, acc.id))


def roll_day(acc: Account, eq: float, today: date | None = None):
    today = today or utcnow().date()
    if acc.day_start_date != today:
        acc.day_start_date, acc.day_start_equity, acc.trades_today = today, eq, 0


def reserved_sell_qty(db: Session, account_id: int, instrument_id: int, exclude_order: int | None = None) -> int:
    q = select(func.coalesce(func.sum(Order.quantity - Order.filled_qty), 0)).where(
        Order.account_id == account_id, Order.instrument_id == instrument_id,
        Order.side == SELL, Order.status == OPEN)
    if exclude_order:
        q = q.where(Order.id != exclude_order)
    return int(db.scalar(q) or 0)


def reserved_buy_cash(db: Session, account_id: int, exclude_order: int | None = None) -> float:
    rows = db.execute(select(Order).where(Order.account_id == account_id, Order.side == BUY,
                                          Order.status == OPEN)).scalars().all()
    total = 0.0
    for o in rows:
        if o.id == exclude_order:
            continue
        px = o.limit_price or o.stop_price or 0.0
        total += (o.quantity - o.filled_qty) * px * 1.003
    return total


def _est_cost(qty: int, px: float) -> float:
    fill = COSTS.fill_price(True, px)
    return qty * fill + COSTS.fees(True, qty * fill)


def pre_trade_checks(db: Session, acc: Account, inst: Instrument, side: str, qty: int, ref_price: float,
                     order_type: str) -> str | None:
    """Return a human-readable rejection reason, or None if the order may go ahead."""
    if getattr(inst, "asset_type", "") == "INDEX" or getattr(inst, "series", "") == "INDEX":
        return f"{inst.symbol} is a benchmark index and cannot be traded directly. Trade individual equities or crypto instead."
    pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == inst.id))
    held = pos.quantity if pos else 0
    if side == SELL:
        free = held - reserved_sell_qty(db, acc.id, inst.id)
        if held <= 0:
            return "Short selling is not allowed: you do not hold this stock"
        if qty > free:
            return f"Insufficient quantity: you can sell at most {max(free, 0)} (open sell orders reserve the rest)"
        return None
    # BUY - exposure limits
    if trading_halted(db):
        return "Trading is halted by the platform kill switch"
    eq = equity(db, acc)
    roll_day(acc, eq)
    if eq <= acc.day_start_equity * (1 - acc.daily_loss_limit_pct):
        return f"Daily loss limit reached ({acc.daily_loss_limit_pct:.0%} of start-of-day equity); new buys blocked until tomorrow"
    if acc.trades_today >= acc.max_daily_trades:
        return f"Daily trade limit reached ({acc.max_daily_trades})"
    if held == 0:
        n_open = db.scalar(select(func.count(Position.id)).where(Position.account_id == acc.id,
                                                                Position.quantity > 0)) or 0
        if n_open >= acc.max_open_positions:
            return f"Max open positions reached ({acc.max_open_positions})"
    if (held + qty) * ref_price > acc.max_position_pct * eq:
        max_qty = int(acc.max_position_pct * eq / ref_price) - held
        return f"Position would exceed {acc.max_position_pct:.0%} of equity (max additional qty: {max(max_qty, 0)})"
    available = acc.cash - reserved_buy_cash(db, acc.id)
    if _est_cost(qty, ref_price) > available:
        return f"Insufficient cash: need about ₹{_est_cost(qty, ref_price):,.2f}, available ₹{available:,.2f}"
    return None


def _publish_order(order: Order, user_id: int, symbol: str):
    hub.publish({"type": "order", "data": {"id": order.id, "symbol": symbol, "side": order.side,
                                           "status": order.status, "qty": order.quantity,
                                           "price": order.avg_fill_price, "reason": order.reject_reason}},
                user_id=user_id)


def fill(db: Session, acc: Account, order: Order, inst: Instrument, ref_price: float) -> Trade:
    """Fill the whole order at ref_price adjusted for slippage. Caller holds the account lock."""
    is_buy = order.side == BUY
    px = round(COSTS.fill_price(is_buy, ref_price), 2)
    if order.order_type == LIMIT:  # a limit order never fills worse than its limit
        px = min(px, order.limit_price) if is_buy else max(px, order.limit_price)
    qty = order.quantity - order.filled_qty
    value = px * qty
    fee = round(COSTS.fees(is_buy, value), 2)
    pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == inst.id))
    realized = 0.0
    if is_buy:
        if value + fee > acc.cash + 1e-6:
            raise OrderRejected("Insufficient cash at fill time")
        acc.cash -= value + fee
        if pos is None:
            pos = Position(account_id=acc.id, instrument_id=inst.id, quantity=0, avg_price=0.0)
            db.add(pos)
        if pos.quantity == 0:
            pos.opened_at, pos.stop_loss, pos.target = utcnow(), None, None
        pos.avg_price = (pos.quantity * pos.avg_price + qty * px) / (pos.quantity + qty)
        pos.quantity += qty
        if order.stop_loss:
            pos.stop_loss = order.stop_loss
        if order.target:
            pos.target = order.target
    else:
        if pos is None or pos.quantity < qty:
            raise OrderRejected("Position changed: not enough quantity to sell")
        acc.cash += value - fee
        realized = (px - pos.avg_price) * qty - fee
        pos.quantity -= qty
        acc.realized_pnl += realized
        if pos.quantity == 0:
            pos.avg_price, pos.stop_loss, pos.target = 0.0, None, None
    acc.fees_paid += fee
    acc.trades_today += 1
    order.filled_qty = order.quantity
    order.avg_fill_price, order.fees, order.status = px, fee, FILLED
    order.updated_at = utcnow()
    t = Trade(order_id=order.id, account_id=acc.id, instrument_id=inst.id, bot_id=order.bot_id, side=order.side,
              quantity=qty, price=px, fees=fee, realized_pnl=round(realized, 2))
    db.add(t)
    db.flush()
    who = {"MANUAL": "by you", "BOT": "by a bot", "SYSTEM": "by your stop-loss or target"}.get(order.source, "")
    pnl_txt = f" Realised P&L ₹{realized:,.2f}." if not is_buy else ""
    verb = "Bought" if is_buy else "Sold"
    notify(db, acc.user_id, "ORDER_FILLED", f"{verb} {qty} {inst.symbol} at ₹{px:,.2f}",
           f"{order.order_type.capitalize()} order #{order.id} placed {who}, charges ₹{fee:,.2f}.{pnl_txt}")
    return t


def place_order(db: Session, account_id: int, inst: Instrument, side: str, order_type: str, quantity: int,
                limit_price: float | None = None, stop_price: float | None = None,
                stop_loss: float | None = None, target: float | None = None,
                source: str = "MANUAL", bot_id: int | None = None) -> Order:
    """Validate, risk-check and (for MARKET) fill an order atomically. Commits.
    Raises OrderRejected (the rejected order is still stored for the audit trail)."""
    side, order_type = side.upper(), order_type.upper()
    with account_lock(account_id):
        acc = lock_account(db, account_id)
        db.refresh(inst)
        order = Order(account_id=acc.id, instrument_id=inst.id, bot_id=bot_id, side=side, order_type=order_type,
                      quantity=int(quantity), limit_price=limit_price, stop_price=stop_price,
                      stop_loss=stop_loss, target=target, source=source, status=OPEN)
        reason = None
        if side not in (BUY, SELL):
            reason = "side must be BUY or SELL"
        elif order_type not in (MARKET, LIMIT, STOP):
            reason = "order_type must be MARKET, LIMIT or STOP"
        elif not isinstance(quantity, int) or quantity <= 0:
            reason = "quantity must be a positive whole number"
        elif order_type == LIMIT and not (limit_price and limit_price > 0):
            reason = "LIMIT orders need a positive limit_price"
        elif order_type == STOP and not (stop_price and stop_price > 0):
            reason = "STOP orders need a positive stop_price"
        elif not inst.is_active or inst.last_price <= 0:
            reason = "Instrument is not tradable"
        elif side == BUY and stop_loss is not None and stop_loss >= (limit_price or stop_price or inst.last_price):
            reason = "stop_loss must be below the buy price"
        elif side == BUY and target is not None and target <= (limit_price or stop_price or inst.last_price):
            reason = "target must be above the buy price"
        if reason is None:
            ref = {MARKET: inst.last_price, LIMIT: limit_price, STOP: stop_price}[order_type]
            reason = pre_trade_checks(db, acc, inst, side, int(quantity), ref, order_type)
        db.add(order)
        db.flush()
        if reason:
            order.status, order.reject_reason = REJECTED, reason[:255]
            db.commit()
            _publish_order(order, acc.user_id, inst.symbol)
            raise OrderRejected(reason, order)
        if order_type == MARKET:
            try:
                fill(db, acc, order, inst, inst.last_price)
            except OrderRejected as e:
                order.status, order.reject_reason = REJECTED, e.reason
                db.commit()
                _publish_order(order, acc.user_id, inst.symbol)
                raise OrderRejected(e.reason, order)
        db.commit()
        _publish_order(order, acc.user_id, inst.symbol)
        return order


def cancel_order(db: Session, account_id: int, order_id: int) -> Order:
    with account_lock(account_id):
        lock_account(db, account_id)
        order = db.get(Order, order_id, populate_existing=True)
        if order is None or order.account_id != account_id:
            raise OrderRejected("Order not found")
        if order.status != OPEN:
            raise OrderRejected(f"Only OPEN orders can be cancelled (this one is {order.status})")
        order.status, order.updated_at = CANCELLED, utcnow()
        db.commit()
        return order


def _triggered(o: Order, price: float) -> bool:
    if o.order_type == LIMIT:
        return price <= o.limit_price if o.side == BUY else price >= o.limit_price
    if o.order_type == STOP:
        return price >= o.stop_price if o.side == BUY else price <= o.stop_price
    return False


def match_open_orders(db: Session, inst: Instrument, price: float) -> int:
    """Fill OPEN limit/stop orders whose condition is met at the new price."""
    ids = db.scalars(select(Order.id).where(Order.instrument_id == inst.id, Order.status == OPEN)).all()
    filled = 0
    for oid in ids:
        o = db.get(Order, oid)
        if o is None or not _triggered(o, price):
            continue
        with account_lock(o.account_id):
            acc = lock_account(db, o.account_id)
            db.refresh(o)
            if o.status != OPEN:
                continue
            ref = price if o.order_type == STOP else (min(price, o.limit_price) if o.side == BUY else max(price, o.limit_price))
            reason = None
            if o.side == BUY:
                if trading_halted(db):
                    reason = "Trading halted by kill switch"
                elif _est_cost(o.quantity, ref) > acc.cash:
                    reason = "Insufficient cash when the order triggered"
            try:
                if reason:
                    raise OrderRejected(reason)
                fill(db, acc, o, inst, ref)
                filled += 1
            except OrderRejected as e:
                o.status, o.reject_reason = REJECTED, e.reason
                notify(db, acc.user_id, "ORDER_REJECTED", f"Order #{o.id} {o.side} {inst.symbol} rejected", e.reason)
            db.commit()
            _publish_order(o, acc.user_id, inst.symbol)
    return filled


def check_protective_exits(db: Session, inst: Instrument, price: float) -> int:
    """Stop-loss / target on manually placed positions -> market SELL (source SYSTEM)."""
    rows = db.execute(select(Position).where(Position.instrument_id == inst.id, Position.quantity > 0)).scalars().all()
    n = 0
    for pos in rows:
        hit = None
        if pos.stop_loss and price <= pos.stop_loss:
            hit = "STOP_LOSS"
        elif pos.target and price >= pos.target:
            hit = "TARGET"
        if not hit:
            continue
        from ..models import Bot  # bot-held quantity is managed by the bot itself
        bot_qty = db.scalar(select(func.coalesce(func.sum(Bot.position_qty), 0)).join(Account, Account.user_id == Bot.user_id)
                            .where(Account.id == pos.account_id, Bot.instrument_id == inst.id)) or 0
        qty = pos.quantity - int(bot_qty) - reserved_sell_qty(db, pos.account_id, inst.id)
        pos.stop_loss = pos.target = None  # one-shot: cleared once triggered
        if qty <= 0:
            db.commit()
            continue
        try:
            place_order(db, pos.account_id, inst, SELL, MARKET, qty, source="SYSTEM")
            n += 1
        except OrderRejected as e:
            log.warning("protective exit failed for position %s: %s", pos.id, e.reason)
    return n


def snapshot_equity(db: Session):
    accs = db.scalars(select(Account)).all()
    now = utcnow()
    for acc in accs:
        eq = equity(db, acc)
        acc.peak_equity = max(acc.peak_equity or eq, eq)
        db.add(EquitySnapshot(account_id=acc.id, ts=now, equity=round(eq, 2), cash=round(acc.cash, 2)))
    db.commit()


def create_account(db: Session, user: User, cash: float) -> Account:
    acc = Account(user_id=user.id, cash=cash, starting_cash=cash, day_start_equity=cash, peak_equity=cash,
                  day_start_date=utcnow().date())
    db.add(acc)
    db.flush()
    return acc


def reset_account(db: Session, account_id: int, cash: float):
    """Wipe positions/orders and restore starting cash (a fresh practice start)."""
    from ..models import Bot, BotStatus
    with account_lock(account_id):
        acc = lock_account(db, account_id)
        running = db.scalars(select(Bot).where(Bot.user_id == acc.user_id,
                                               Bot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))).all()
        for b in running:
            b.status = BotStatus.STOPPED
        for b in db.scalars(select(Bot).where(Bot.user_id == acc.user_id)).all():
            b.position_qty, b.entry_price, b.stop_price, b.target_price, b.extreme_price = 0, None, None, None, None
        for o in db.scalars(select(Order).where(Order.account_id == acc.id, Order.status == OPEN)).all():
            o.status = CANCELLED
        for p in db.scalars(select(Position).where(Position.account_id == acc.id)).all():
            db.delete(p)
        db.query(EquitySnapshot).filter(EquitySnapshot.account_id == acc.id).delete()
        acc.cash = acc.starting_cash = acc.day_start_equity = acc.peak_equity = cash
        acc.realized_pnl = acc.fees_paid = 0.0
        acc.trades_today, acc.day_start_date = 0, utcnow().date()
        db.commit()
