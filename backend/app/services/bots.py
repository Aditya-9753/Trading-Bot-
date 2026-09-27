"""Bot manager: evaluates RUNNING bots on every closed practice bar (in the resource-limited sandbox),
places orders through the paper broker, and enforces stop / target / trailing stop on every tick.

Lifecycle: DRAFT -> (backtest) -> BACKTESTED -> RUNNING <-> PAUSED -> STOPPED;  any -> ERROR on failure.
Editing parameters sends the bot back to DRAFT: it must be backtested again with the new parameters.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bots.bot_sandbox import SandboxError, SandboxLimits, run_sandboxed
from ..core.config import settings
from ..models import Account, Bot, BotLog, BotStatus, Instrument, Position, utcnow
from ..risk import position_sizer, risk_engine, stop_loss
from ..strategies.engine.strategy_engine import evaluate
from ..strategies.params import Side
from . import broker
from .events import notify
from .market_data import load_df, trading_halted
from .realtime import hub
from .strategy import build_params

log = logging.getLogger(__name__)


def limits() -> SandboxLimits:
    return SandboxLimits(wall_timeout_s=settings.BOT_TIMEOUT_S, cpu_seconds=settings.BOT_CPU_S,
                         memory_mb=settings.BOT_MEMORY_MB)


def bot_log(db: Session, bot: Bot, event: str, message: str, level: str = "INFO", data: dict | None = None):
    db.add(BotLog(bot_id=bot.id, event=event, message=message[:500], level=level, data=data))
    hub.publish({"type": "bot", "data": {"id": bot.id, "status": bot.status, "event": event, "message": message[:200],
                                         "level": level}}, user_id=bot.user_id)


def account_of(db: Session, bot: Bot) -> Account:
    return db.scalar(select(Account).where(Account.user_id == bot.user_id))


def _clear_position(bot: Bot):
    bot.position_qty, bot.entry_price, bot.stop_price, bot.target_price, bot.extreme_price = 0, None, None, None, None


def exit_position(db: Session, bot: Bot, inst: Instrument, reason: str) -> bool:
    if bot.position_qty <= 0:
        return False
    acc = account_of(db, bot)
    pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == inst.id))
    qty = min(bot.position_qty, pos.quantity if pos else 0)
    if qty <= 0:
        bot_log(db, bot, "RECONCILE", "Position no longer held in the account; bot position cleared", "WARN")
        _clear_position(bot)
        db.commit()
        return False
    entry = bot.entry_price or 0
    try:
        order = broker.place_order(db, acc.id, inst, broker.SELL, broker.MARKET, qty, source="BOT", bot_id=bot.id)
    except broker.OrderRejected as e:
        bot_log(db, bot, "EXIT_REJECTED", f"Exit ({reason}) rejected: {e.reason}", "WARN")
        db.commit()
        return False
    pnl = (order.avg_fill_price - entry) * qty - order.fees
    bot.realized_pnl += pnl
    bot.trade_count += 1
    bot_log(db, bot, "EXIT", f"{reason}: sold {qty} at ₹{order.avg_fill_price:,.2f}, P&L ₹{pnl:,.2f}",
            data={"reason": reason, "order_id": order.id, "pnl": round(pnl, 2)})
    _clear_position(bot)
    db.commit()
    return True


def _reconcile(db: Session, bot: Bot, acc: Account):
    """If the user sold the bot's shares manually, don't let the bot think it still holds them."""
    if bot.position_qty <= 0:
        return
    pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == bot.instrument_id))
    held = pos.quantity if pos else 0
    if held < bot.position_qty:
        bot_log(db, bot, "RECONCILE", f"Account holds {held}, bot thought {bot.position_qty}; adjusted", "WARN")
        bot.position_qty = held
        if held == 0:
            _clear_position(bot)


def set_error(db: Session, bot: Bot, message: str):
    bot.status, bot.error_message = BotStatus.ERROR, message[:2000]
    bot_log(db, bot, "ERROR", message[:500], "ERROR")
    notify(db, bot.user_id, "BOT_ERROR", f"Bot '{bot.name}' stopped with an error", message[:300])
    db.commit()


def evaluate_bot(db: Session, bot: Bot, inst: Instrument, df) -> dict | None:
    acc = account_of(db, bot)
    _reconcile(db, bot, acc)
    p = build_params(bot.algorithm_version, bot.params or {})
    side = Side.LONG if bot.position_qty > 0 else None
    try:
        decision = run_sandboxed(evaluate, df, p, side, limits=limits())
    except SandboxError as e:
        set_error(db, bot, f"Evaluation failed in sandbox: {e}")
        return None
    bot.last_decision, bot.last_evaluated_at = decision, utcnow()
    bar = df.iloc[-1]
    action = decision["action"]

    if bot.position_qty > 0:
        # trailing stop from the extreme since entry (only ever tightens)
        bot.extreme_price = max(bot.extreme_price or bot.entry_price, float(bar["high"]))
        cand = stop_loss.trailing_stop(Side.LONG, bot.extreme_price, decision["atr"], p)
        new_stop = stop_loss.tighten(Side.LONG, bot.stop_price, cand)
        if new_stop != bot.stop_price:
            bot_log(db, bot, "TRAIL", f"Stop raised from ₹{bot.stop_price:,.2f} to ₹{new_stop:,.2f}")
            bot.stop_price = round(new_stop, 2)
        if action == "EXIT":
            db.commit()
            exit_position(db, bot, inst, f"Signal exit (S={decision['S']:+.2f})")
            return decision
    elif action == "BUY" and bot.status == BotStatus.RUNNING:
        if trading_halted(db):
            bot_log(db, bot, "SKIP", "BUY signal ignored: platform kill switch active", "WARN")
        else:
            price = inst.last_price
            eq = broker.equity(db, acc)
            dd = max(0.0, 1 - eq / acc.peak_equity) if acc.peak_equity else 0.0
            conv = risk_engine.conviction_factor(decision["confidence"] / 100, Side.LONG, p)
            ra = risk_engine.assess(decision["vol_ratio"], dd, conv, p)
            capital = max(0.0, bot.capital_allocation + bot.realized_pnl)
            bp = min(acc.cash, capital) * p.max_buying_power_use
            sz = position_sizer.size(capital, decision["atr"], conv, ra.risk_score, p, price, bp)
            info = {"S": decision["S"], "regime": decision["regime"], "risk_score": round(ra.risk_score, 3),
                    "qty": sz.quantity, "capped_by_cash": sz.capped_by_cash}
            if sz.quantity <= 0:
                bot_log(db, bot, "SKIP", "BUY signal but position size is 0 (risk too high or capital too low)",
                        "WARN", info)
            else:
                try:
                    order = broker.place_order(db, acc.id, inst, broker.BUY, broker.MARKET, sz.quantity,
                                               source="BOT", bot_id=bot.id)
                    lv = stop_loss.initial_levels(Side.LONG, order.avg_fill_price, decision["atr"], p)
                    bot.position_qty, bot.entry_price = sz.quantity, order.avg_fill_price
                    bot.stop_price, bot.target_price = round(lv.stop_loss, 2), round(lv.take_profit, 2)
                    bot.extreme_price = order.avg_fill_price
                    bot_log(db, bot, "ENTRY", f"Bought {sz.quantity} at ₹{order.avg_fill_price:,.2f}, stop ₹{bot.stop_price:,.2f}, target ₹{bot.target_price:,.2f}",
                            data={**info, "order_id": order.id})
                except broker.OrderRejected as e:
                    bot_log(db, bot, "ORDER_REJECTED", f"BUY {sz.quantity} rejected: {e.reason}", "WARN", info)
    else:
        bot_log(db, bot, "EVAL", f"{action.capitalize()}: S {decision['S']:+.3f}, regime {decision['regime'].replace('_', ' ').lower()}",
                data={"S": decision["S"], "regime": decision["regime"]})
    db.commit()
    return decision


def on_bar_close(db: Session, inst: Instrument):
    bots = db.scalars(select(Bot).where(Bot.instrument_id == inst.id,
                                        Bot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))).all()
    if not bots:
        return
    df = load_df(db, inst.id, limit=settings.BOT_HISTORY_BARS)
    for bot in bots:
        try:
            if bot.status == BotStatus.PAUSED and bot.position_qty <= 0:
                continue
            evaluate_bot(db, bot, inst, df)
        except Exception as e:  # never let one bot break the market loop
            db.rollback()
            log.exception("bot %s failed", bot.id)
            bot = db.get(Bot, bot.id)
            set_error(db, bot, f"Unexpected error: {e}")


def on_tick(db: Session, inst: Instrument, price: float):
    bots = db.scalars(select(Bot).where(Bot.instrument_id == inst.id, Bot.position_qty > 0,
                                        Bot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))).all()
    for bot in bots:
        if bot.stop_price and price <= bot.stop_price:
            exit_position(db, bot, inst, f"Stop-loss hit (₹{bot.stop_price:,.2f})")
        elif bot.target_price and price >= bot.target_price:
            exit_position(db, bot, inst, f"Target hit (₹{bot.target_price:,.2f})")


def kill_bot(db: Session, bot: Bot, reason: str = "Kill switch"):
    """Stop immediately AND flatten the bot's position."""
    inst = db.get(Instrument, bot.instrument_id)
    for o in db.scalars(select(broker.Order).where(broker.Order.bot_id == bot.id, broker.Order.status == broker.OPEN)).all():
        o.status = broker.CANCELLED
    if bot.position_qty > 0:
        exit_position(db, bot, inst, reason)
    bot.status = BotStatus.STOPPED
    bot_log(db, bot, "KILLED", reason, "WARN")
    db.commit()


def stop_bot(db: Session, bot: Bot):
    """Stop without selling: the shares stay in the account, protected by the bot's last stop/target."""
    if bot.position_qty > 0:
        acc = account_of(db, bot)
        pos = db.scalar(select(Position).where(Position.account_id == acc.id, Position.instrument_id == bot.instrument_id))
        if pos:
            pos.stop_loss, pos.target = bot.stop_price, bot.target_price
        bot_log(db, bot, "HANDOVER", f"{bot.position_qty} shares handed to your portfolio with stop ₹{bot.stop_price} / target ₹{bot.target_price}")
    _clear_position(bot)
    bot.status = BotStatus.STOPPED
    bot_log(db, bot, "STOPPED", "Bot stopped")
    db.commit()
