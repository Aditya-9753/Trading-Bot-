import os

import pytest
from sqlalchemy import select

from app.bots.bot_sandbox import SandboxError
from app.core.db import SessionLocal
from app.models import Bot, Candle, Instrument
from app.services import bots as bot_svc
from app.services.market_data import load_df
from app.services.simulator import Simulator

from .conftest import login, register

API = "/api/v1"


def test_strategy_params_and_evaluate(client, user):
    p = client.get(f"{API}/strategy/params", headers=user["h"]).json()
    assert p["default_version"] == "1.2" and "entry_score" in {t["name"] for t in p["tunable"]}
    r = client.post(f"{API}/strategy/evaluate", headers=user["h"], json={"symbol": "RELIANCE", "bars": 100})
    assert r.status_code == 200
    d = r.json()
    assert len(d["series"]) == 100 and d["decision"]["action"] in ("BUY", "HOLD", "SELL", "EXIT")
    assert set(d["latest"]["contributions"]) == {"trend", "momentum", "reversion", "volume"}
    r = client.post(f"{API}/strategy/evaluate", headers=user["h"], json={"symbol": "RELIANCE", "version": "1.1"})
    assert len(r.json()["latest"]["contributions"]) == 6


def test_param_validation(client, user):
    for bad in ({"entry_score": 5}, {"hack": 1}, {"fast_ema": 60, "slow_ema": 50}):
        r = client.post(f"{API}/strategy/evaluate", headers=user["h"], json={"symbol": "TCS", "params": bad})
        assert r.status_code == 422, bad


def test_backtest_with_walk_forward(client, user):
    r = client.post(f"{API}/backtests", headers=user["h"],
                    json={"symbol": "TCS", "walk_forward": True, "initial_capital": 500000})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "DONE" and b["equity_curve"] and b["benchmark_curve"]
    assert b["metrics"]["trade_count"] is not None and b["walk_forward"]
    lst = client.get(f"{API}/backtests", headers=user["h"]).json()
    assert lst[0]["id"] == b["id"] and "equity_curve" not in lst[0]
    other = register(client)
    assert client.get(f"{API}/backtests/{b['id']}", headers=other["h"]).status_code == 404


def _bot(client, h, **kw):
    body = {"name": "Test bot", "symbol": "RELIANCE", "capital_allocation": 200000, **kw}
    r = client.post(f"{API}/bots", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_bot_lifecycle_requires_backtest(client, user):
    h = user["h"]
    b = _bot(client, h)
    assert b["status"] == "DRAFT"
    assert client.post(f"{API}/bots/{b['id']}/start", headers=h).status_code == 409
    r = client.post(f"{API}/bots/{b['id']}/backtest", headers=h, json={"walk_forward": False})
    assert r.status_code == 200 and r.json()["bot"]["status"] == "BACKTESTED"
    assert client.post(f"{API}/bots/{b['id']}/start", headers=h).json()["status"] == "RUNNING"
    assert client.patch(f"{API}/bots/{b['id']}", headers=h, json={"params": {"entry_score": 0.6}}).status_code == 409
    assert client.post(f"{API}/bots/{b['id']}/pause", headers=h).json()["status"] == "PAUSED"
    assert client.post(f"{API}/bots/{b['id']}/resume", headers=h).json()["status"] == "RUNNING"
    assert client.post(f"{API}/bots/{b['id']}/stop", headers=h).json()["status"] == "STOPPED"
    # editing params -> back to DRAFT, must re-backtest
    r = client.patch(f"{API}/bots/{b['id']}", headers=h, json={"params": {"entry_score": 0.6}})
    assert r.json()["status"] == "DRAFT" and r.json()["backtest_current"] is False
    assert client.post(f"{API}/bots/{b['id']}/start", headers=h).status_code == 409
    logs = client.get(f"{API}/bots/{b['id']}/logs", headers=h).json()
    assert {"CREATED", "BACKTESTED", "STARTED", "EDITED"} <= {l["event"] for l in logs}
    assert client.delete(f"{API}/bots/{b['id']}", headers=h).status_code == 200


def _running_bot(client, h, symbol="RELIANCE"):
    b = _bot(client, h, symbol=symbol)
    client.post(f"{API}/bots/{b['id']}/backtest", headers=h, json={"walk_forward": False})
    client.post(f"{API}/bots/{b['id']}/start", headers=h)
    return b


def _decision(action, atr=20.0):
    return {"algorithm_version": "1.2", "time": "x", "regime": "TRENDING", "S": 0.7 if action == "BUY" else -0.4,
            "confidence": 85.0, "atr": atr, "vol_ratio": 1.0, "contributions": {}, "action": action}


def _eval_now(bot_id):
    with SessionLocal() as db:
        bot = db.get(Bot, bot_id)
        inst = db.get(Instrument, bot.instrument_id)
        bot_svc.on_bar_close(db, inst)


def test_bot_entry_trailing_and_stop_exit(client, user, monkeypatch):
    h = user["h"]
    b = _running_bot(client, h)
    monkeypatch.setattr(bot_svc, "run_sandboxed", lambda fn, *a, **k: _decision("BUY"))
    _eval_now(b["id"])
    bot = client.get(f"{API}/bots/{b['id']}", headers=h).json()
    assert bot["position_qty"] > 0 and bot["stop_price"] < bot["entry_price"] < bot["target_price"]
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert pf["positions"][0]["bot_quantity"] == bot["position_qty"]
    # a price below the stop on the next tick closes the bot position
    with SessionLocal() as db:
        inst = db.scalar(select(Instrument).where(Instrument.symbol == "RELIANCE"))
        orig = inst.last_price
        inst.last_price = round(bot["stop_price"] - 1, 2)
        db.commit()
        bot_svc.on_tick(db, inst, inst.last_price)
        inst.last_price = orig
        db.commit()
    bot = client.get(f"{API}/bots/{b['id']}", headers=h).json()
    assert bot["position_qty"] == 0 and bot["trade_count"] == 1
    assert any(l["event"] == "EXIT" and "Stop-loss" in l["message"] for l in client.get(f"{API}/bots/{b['id']}/logs", headers=h).json())
    client.post(f"{API}/bots/{b['id']}/stop", headers=h)


def test_bot_sandbox_failure_sets_error(client, user, monkeypatch):
    h = user["h"]
    b = _running_bot(client, h, "TCS")

    def boom(*a, **k):
        raise SandboxError("evaluation process died")
    monkeypatch.setattr(bot_svc, "run_sandboxed", boom)
    _eval_now(b["id"])
    bot = client.get(f"{API}/bots/{b['id']}", headers=h).json()
    assert bot["status"] == "ERROR" and "sandbox" in bot["error_message"]
    assert any(n["kind"] == "BOT_ERROR" for n in client.get(f"{API}/notifications", headers=h).json()["items"])


def test_bot_kill_flattens_position(client, user, monkeypatch):
    h = user["h"]
    b = _running_bot(client, h, "INFY")
    monkeypatch.setattr(bot_svc, "run_sandboxed", lambda fn, *a, **k: _decision("BUY"))
    _eval_now(b["id"])
    assert client.get(f"{API}/bots/{b['id']}", headers=h).json()["position_qty"] > 0
    r = client.post(f"{API}/bots/{b['id']}/kill", headers=h).json()
    assert r["status"] == "STOPPED" and r["position_qty"] == 0
    assert client.get(f"{API}/portfolio", headers=h).json()["positions"] == []


def test_real_sandbox_evaluation_via_simulator(client, user):
    """No mocks: simulator closes a practice bar and the bot is evaluated in the real sandbox process."""
    h = user["h"]
    b = _running_bot(client, h, "HINDUNILVR")
    sim = Simulator(seed=1)
    with SessionLocal() as db:
        inst = db.scalar(select(Instrument).where(Instrument.symbol == "HINDUNILVR"))
        n_before = len(load_df(db, inst.id))
    for _ in range(int(os.environ["TICKS_PER_BAR"])):
        sim.step()
    with SessionLocal() as db:
        assert len(load_df(db, inst.id)) == n_before + 1
        src = db.scalars(select(Candle.source).where(Candle.instrument_id == inst.id).order_by(Candle.ts.desc()).limit(1)).first()
        assert src == "SIMULATED"
    bot = client.get(f"{API}/bots/{b['id']}", headers=h).json()
    assert bot["status"] in ("RUNNING",) and bot["last_decision"]["algorithm_version"] == "1.2"
    assert client.get(f"{API}/portfolio/equity", headers=h).json()
    client.post(f"{API}/bots/{b['id']}/kill", headers=h)


def test_admin_permissions_and_kill_switch(client, user, admin_h):
    h = user["h"]
    assert client.get(f"{API}/admin/stats", headers=h).status_code == 403
    assert client.post(f"{API}/admin/kill-switch", headers=h, json={"active": True}).status_code == 403
    b = _running_bot(client, h, "SBIN")
    client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 5})
    r = client.post(f"{API}/admin/kill-switch", headers=admin_h, json={"active": True, "reason": "test"}).json()
    assert r["active"] and r["bots_stopped"] >= 1
    assert client.get(f"{API}/bots/{b['id']}", headers=h).json()["status"] == "STOPPED"
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 1})
    assert r.status_code == 400 and "kill switch" in r.json()["detail"]["message"]
    assert client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "SELL", "quantity": 5}).status_code == 201
    assert client.post(f"{API}/bots/{b['id']}/start", headers=h).status_code == 423
    client.post(f"{API}/admin/kill-switch", headers=admin_h, json={"active": False})
    audit = client.get(f"{API}/admin/audit?action=admin.kill", headers=admin_h).json()
    assert len(audit) >= 2
    assert client.get(f"{API}/admin/stats", headers=admin_h).json()["users"] >= 2


def test_admin_cannot_change_roles_but_super_admin_can(client, admin_h):
    u = register(client)
    assert client.patch(f"{API}/admin/users/{u['id']}", headers=admin_h, json={"role": "ADMIN"}).status_code == 200
    ah = login(client, u["email"], u["password"])
    v = register(client)
    assert client.patch(f"{API}/admin/users/{v['id']}", headers=ah, json={"role": "ADMIN"}).status_code == 403
    assert client.patch(f"{API}/admin/users/{v['id']}", headers=ah, json={"is_active": False}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": v["email"], "password": v["password"]}).status_code == 403


def test_websocket(client, user):
    with client.websocket_connect(f"{API}/ws?token={user['token']}") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_text("ping")
        assert ws.receive_json()["type"] == "pong"
    with pytest.raises(Exception):
        with client.websocket_connect(f"{API}/ws?token=bad") as ws:
            ws.receive_json()


@pytest.mark.skipif(not os.getenv("TEST_MYSQL_URL"), reason="set TEST_MYSQL_URL to run against MySQL")
def test_mysql_row_lock_concurrency():
    """Same overdraw test against real MySQL row locks (SELECT ... FOR UPDATE) with separate engines."""
    import threading
    from sqlalchemy.orm import sessionmaker
    from app.core.db import Base, make_engine
    from app.models import Account, User
    from app.services import broker
    eng = make_engine(os.environ["TEST_MYSQL_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    with S() as db:
        u = User(email="m@example.com", password_hash="x")
        db.add(u)
        db.flush()
        acc = broker.create_account(db, u, 1_000_000)
        acc.max_position_pct = 1.0
        inst = Instrument(symbol="X", name="X", last_price=100.0, prev_close=100.0)
        db.add(inst)
        db.commit()
        acc_id, inst_id = acc.id, inst.id
    broker._locks.clear()
    results = []

    def worker():
        with S() as db:
            broker._locks[acc_id] = __import__("threading").RLock()  # defeat the in-process lock: DB lock must hold
            try:
                broker.place_order(db, acc_id, db.get(Instrument, inst_id), "BUY", "MARKET", 3000)
                results.append(1)
            except broker.OrderRejected:
                results.append(0)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(results) == 3
