"""Strategy lab, backtests and bots."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models import Backtest, Bot, BotLog, BotStatus, Instrument, User, utcnow
from ...services import bots as bot_svc
from ...services import strategy as strat
from ...services.events import audit
from ...services.market_data import load_df, trading_halted
from ..deps import current_account, current_user, instrument_or_404
from .trading import iso

router = APIRouter(tags=["strategy"])


def _params_or_422(version: str, params: dict):
    try:
        return strat.build_params(version, params)
    except strat.ParamError as e:
        raise HTTPException(422, str(e))


@router.get("/strategy/params")
def strategy_params(version: str = "1.2", _: User = Depends(current_user)):
    if version not in strat.VERSIONS:
        raise HTTPException(404, "Unknown version")
    p = strat.VERSIONS[version]
    return {"versions": list(strat.VERSIONS), "default_version": "1.2", "version": version,
            "tunable": [{"name": k, "min": lo, "max": hi, "type": typ.__name__, "label": label, "help": help_,
                         "default": getattr(p, k)} for k, (lo, hi, typ, label, help_) in strat.TUNABLE.items()],
            "components": list(p.components), "weights": p.weights,
            "notes": "v1.2 is the default. v1.1 is kept unchanged for comparison (see CHANGELOG_v1_2.md)."}


class EvalIn(BaseModel):
    symbol: str
    version: str = "1.2"
    params: dict = Field(default_factory=dict)
    bars: int = Field(default=200, ge=20, le=1000)


@router.post("/strategy/evaluate")
def evaluate(body: EvalIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    p = _params_or_422(body.version, body.params)
    inst = instrument_or_404(db, body.symbol)
    df = load_df(db, inst.id, limit=body.bars + p.warmup_bars + 50)
    if len(df) < p.warmup_bars + 2:
        raise HTTPException(400, f"Not enough history for {inst.symbol}")
    from ...strategies.engine.strategy_engine import evaluate as engine_eval
    out = strat.signal_series(df, p, body.bars)
    out["decision"] = strat.clean_dict({k: v for k, v in engine_eval(df, p).items()
                                        if k not in ("contributions",)})
    out["symbol"] = inst.symbol
    out["simulated"] = True
    return out


# ---- backtests -----------------------------------------------------------------
class BacktestIn(BaseModel):
    symbol: str
    version: str = "1.2"
    params: dict = Field(default_factory=dict)
    initial_capital: float = Field(default=1_000_000, ge=10_000, le=1e9)
    walk_forward: bool = False
    robustness: bool = False
    bars: int | None = Field(default=None, ge=200, le=5000)


def bt_out(b: Backtest, symbol: str, full: bool = True) -> dict:
    d = {"id": b.id, "symbol": symbol, "bot_id": b.bot_id, "algorithm_version": b.algorithm_version,
         "params": b.params, "initial_capital": b.initial_capital, "status": b.status, "bars": b.bars,
         "start": iso(b.start_ts), "end": iso(b.end_ts), "metrics": b.metrics, "error": b.error,
         "created_at": iso(b.created_at), "has_walk_forward": bool(b.walk_forward), "has_robustness": bool(b.robustness)}
    if full:
        d.update({"equity_curve": (b.equity_curve or {}).get("strategy") if isinstance(b.equity_curve, dict) else b.equity_curve,
                  "benchmark_curve": (b.equity_curve or {}).get("benchmark") if isinstance(b.equity_curve, dict) else None,
                  "trades": b.trades, "walk_forward": b.walk_forward, "robustness": b.robustness})
    return d


def run_and_store(db: Session, user_id: int, inst: Instrument, version: str, params: dict, capital: float,
                  wf: bool, rb: bool, bars: int | None = None, bot_id: int | None = None) -> Backtest:
    df = load_df(db, inst.id, limit=bars)
    from datetime import datetime
    b = Backtest(user_id=user_id, instrument_id=inst.id, bot_id=bot_id, algorithm_version=version, params=params,
                 params_hash=strat.params_hash(version, params), initial_capital=capital)
    try:
        r = strat.run(df, version, params, capital, wf, rb)
        b.metrics, b.trades, b.walk_forward, b.robustness = r["metrics"], r["trades"], r["walk_forward"], r["robustness"]
        b.equity_curve = {"strategy": r["equity_curve"], "benchmark": r["benchmark_curve"]}
        b.bars = r["bars"]
        b.start_ts = datetime.fromisoformat(r["start"])
        b.end_ts = datetime.fromisoformat(r["end"])
        b.status = "DONE"
    except strat.ParamError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # keep a record of failures
        b.status, b.error = "FAILED", str(e)[:2000]
    db.add(b)
    db.commit()
    return b


@router.post("/backtests", status_code=201)
def create_backtest(body: BacktestIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _params_or_422(body.version, body.params)
    inst = instrument_or_404(db, body.symbol)
    b = run_and_store(db, user.id, inst, body.version, body.params, body.initial_capital,
                      body.walk_forward, body.robustness, body.bars)
    return bt_out(b, inst.symbol)


@router.get("/backtests")
def list_backtests(limit: int = Query(50, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(Backtest, Instrument.symbol).join(Instrument, Instrument.id == Backtest.instrument_id)
                      .where(Backtest.user_id == user.id).order_by(Backtest.id.desc()).limit(limit)).all()
    return [bt_out(b, s, full=False) for b, s in rows]


def _own_bt(db, bid, user) -> Backtest:
    b = db.get(Backtest, bid)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "Backtest not found")
    return b


@router.get("/backtests/{bid}")
def get_backtest(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bt(db, bid, user)
    return bt_out(b, db.get(Instrument, b.instrument_id).symbol)


@router.delete("/backtests/{bid}")
def delete_backtest(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(_own_bt(db, bid, user))
    db.commit()
    return {"ok": True}


# ---- bots ----------------------------------------------------------------------
class BotIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    symbol: str
    version: str = "1.2"
    params: dict = Field(default_factory=dict)
    capital_allocation: float = Field(ge=10_000, le=1e9)


class BotPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    params: dict | None = None
    version: str | None = None
    capital_allocation: float | None = Field(default=None, ge=10_000, le=1e9)


def bot_out(db: Session, b: Bot) -> dict:
    inst = db.get(Instrument, b.instrument_id)
    unreal = (inst.last_price - b.entry_price) * b.position_qty if b.position_qty and b.entry_price else 0.0
    return {"id": b.id, "name": b.name, "symbol": inst.symbol, "algorithm_version": b.algorithm_version,
            "params": b.params or {}, "capital_allocation": b.capital_allocation, "status": b.status,
            "position_qty": b.position_qty, "entry_price": b.entry_price, "stop_price": b.stop_price,
            "target_price": b.target_price, "last_price": inst.last_price,
            "unrealized_pnl": round(unreal, 2), "realized_pnl": round(b.realized_pnl, 2), "trade_count": b.trade_count,
            "last_decision": b.last_decision, "last_evaluated_at": iso(b.last_evaluated_at),
            "last_backtest_id": b.last_backtest_id,
            "backtest_current": b.backtested_params_hash == strat.params_hash(b.algorithm_version, b.params or {}),
            "error_message": b.error_message, "created_at": iso(b.created_at)}


def _own_bot(db, bid, user) -> Bot:
    b = db.get(Bot, bid)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "Bot not found")
    return b


@router.get("/bots")
def list_bots(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [bot_out(db, b) for b in db.scalars(select(Bot).where(Bot.user_id == user.id).order_by(Bot.id.desc()))]


@router.post("/bots", status_code=201)
def create_bot(body: BotIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _params_or_422(body.version, body.params)
    inst = instrument_or_404(db, body.symbol)
    if db.scalar(select(func.count(Bot.id)).where(Bot.user_id == user.id)) >= 20:
        raise HTTPException(400, "You can have at most 20 bots")
    b = Bot(user_id=user.id, name=body.name.strip(), instrument_id=inst.id, algorithm_version=body.version,
            params=body.params, capital_allocation=body.capital_allocation, status=BotStatus.DRAFT)
    db.add(b)
    db.flush()
    bot_svc.bot_log(db, b, "CREATED", f"Bot created on {inst.symbol} (algorithm v{body.version})")
    db.commit()
    return bot_out(db, b)


@router.get("/bots/{bid}")
def get_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return bot_out(db, _own_bot(db, bid, user))


@router.patch("/bots/{bid}")
def update_bot(bid: int, body: BotPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    if b.status in (BotStatus.RUNNING, BotStatus.PAUSED) and (body.params is not None or body.version is not None):
        raise HTTPException(409, "Stop the bot before changing its strategy parameters")
    if body.name is not None:
        b.name = body.name.strip()
    if body.capital_allocation is not None:
        b.capital_allocation = body.capital_allocation
    if body.params is not None or body.version is not None:
        version = body.version or b.algorithm_version
        params = body.params if body.params is not None else (b.params or {})
        _params_or_422(version, params)
        b.algorithm_version, b.params = version, params
        if strat.params_hash(version, params) != b.backtested_params_hash:
            b.status = BotStatus.DRAFT
            bot_svc.bot_log(db, b, "EDITED", "Parameters changed; bot must be backtested again before it can run")
    db.commit()
    return bot_out(db, b)


@router.delete("/bots/{bid}")
def delete_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    if b.status in (BotStatus.RUNNING, BotStatus.PAUSED) or b.position_qty > 0:
        raise HTTPException(409, "Stop the bot (and close its position) before deleting it")
    db.delete(b)
    db.commit()
    return {"ok": True}


class BotBacktestIn(BaseModel):
    walk_forward: bool = True
    robustness: bool = False


@router.post("/bots/{bid}/backtest")
def backtest_bot(bid: int, body: BotBacktestIn = BotBacktestIn(), db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    inst = db.get(Instrument, b.instrument_id)
    bt = run_and_store(db, user.id, inst, b.algorithm_version, b.params or {}, b.capital_allocation,
                       body.walk_forward, body.robustness, bot_id=b.id)
    if bt.status != "DONE":
        bot_svc.bot_log(db, b, "BACKTEST_FAILED", bt.error or "backtest failed", "ERROR")
        db.commit()
        raise HTTPException(400, f"Backtest failed: {bt.error}")
    b.last_backtest_id, b.backtested_params_hash = bt.id, bt.params_hash
    if b.status in (BotStatus.DRAFT, BotStatus.STOPPED, BotStatus.ERROR, BotStatus.BACKTESTED):
        b.status, b.error_message = BotStatus.BACKTESTED, None
    m = bt.metrics or {}
    bot_svc.bot_log(db, b, "BACKTESTED", f"Backtest #{bt.id}: {m.get('trade_count', 0):.0f} trades, return {(m.get('total_return') or 0) * 100:+.2f}%",
                    data={"backtest_id": bt.id})
    db.commit()
    return {"bot": bot_out(db, b), "backtest": bt_out(bt, inst.symbol)}


def _transition(db, b: Bot, allowed: tuple, new: str, event: str, msg: str):
    if b.status not in allowed:
        raise HTTPException(409, f"Cannot {event.lower()} a bot in {b.status} state")
    b.status = new
    bot_svc.bot_log(db, b, event, msg)
    db.commit()


@router.post("/bots/{bid}/start")
def start_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user),
              acc=Depends(current_account)):
    b = _own_bot(db, bid, user)
    if trading_halted(db):
        raise HTTPException(423, "Trading is halted by the platform kill switch")
    if b.backtested_params_hash != strat.params_hash(b.algorithm_version, b.params or {}):
        raise HTTPException(409, "Backtest this bot with its current parameters before starting it")
    if b.capital_allocation > acc.cash + 1 and b.position_qty == 0:
        raise HTTPException(400, f"Capital allocation ₹{b.capital_allocation:,.0f} exceeds available cash ₹{acc.cash:,.0f}")
    b.error_message = None
    _transition(db, b, (BotStatus.BACKTESTED, BotStatus.STOPPED, BotStatus.ERROR), BotStatus.RUNNING, "STARTED",
                "Bot started: evaluates on every closed practice bar")
    audit(db, user.id, "bot.start", f"bot:{b.id}")
    db.commit()
    return bot_out(db, b)


@router.post("/bots/{bid}/pause")
def pause_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    _transition(db, b, (BotStatus.RUNNING,), BotStatus.PAUSED, "PAUSED",
                "Paused: no new entries; an open position stays protected by stop/target and exit signals")
    return bot_out(db, b)


@router.post("/bots/{bid}/resume")
def resume_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    if trading_halted(db):
        raise HTTPException(423, "Trading is halted by the platform kill switch")
    _transition(db, b, (BotStatus.PAUSED,), BotStatus.RUNNING, "RESUMED", "Bot resumed")
    return bot_out(db, b)


@router.post("/bots/{bid}/stop")
def stop_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    if b.status not in (BotStatus.RUNNING, BotStatus.PAUSED, BotStatus.ERROR):
        raise HTTPException(409, f"Bot is not running ({b.status})")
    bot_svc.stop_bot(db, b)
    return bot_out(db, b)


@router.post("/bots/{bid}/kill")
def kill_bot(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    bot_svc.kill_bot(db, b, "Kill switch pressed by user: position closed at market")
    audit(db, user.id, "bot.kill", f"bot:{b.id}")
    db.commit()
    return bot_out(db, b)


@router.get("/bots/{bid}/logs")
def bot_logs(bid: int, limit: int = Query(200, le=1000), level: str = "", db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    b = _own_bot(db, bid, user)
    stmt = select(BotLog).where(BotLog.bot_id == b.id)
    if level:
        stmt = stmt.where(BotLog.level == level.upper())
    rows = db.scalars(stmt.order_by(BotLog.id.desc()).limit(limit)).all()
    return [{"id": r.id, "ts": iso(r.ts), "level": r.level, "event": r.event, "message": r.message, "data": r.data}
            for r in rows]
