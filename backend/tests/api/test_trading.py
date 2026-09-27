import threading

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Account, Instrument
from app.services import broker
from app.services.simulator import check_alerts

API = "/api/v1"


def price(client, h, sym="ITC"):
    return client.get(f"{API}/markets/{sym}", headers=h).json()["last_price"]


def set_price(sym, px):
    with SessionLocal() as db:
        inst = db.scalar(select(Instrument).where(Instrument.symbol == sym))
        inst.last_price = px
        db.commit()


def tick(sym, px):
    """Simulate a tick: move the price and run the per-tick processing."""
    set_price(sym, px)
    with SessionLocal() as db:
        inst = db.scalar(select(Instrument).where(Instrument.symbol == sym))
        broker.match_open_orders(db, inst, px)
        broker.check_protective_exits(db, inst, px)
        check_alerts(db, inst, px)


def test_markets_and_candles(client, user):
    rows = client.get(f"{API}/markets", headers=user["h"]).json()
    assert {"RELIANCE", "TCS", "ITC"} <= {r["symbol"] for r in rows} and len(rows) >= 12
    c = client.get(f"{API}/markets/RELIANCE/candles?bars=100", headers=user["h"]).json()
    assert len(c["candles"]) == 100 and len(c["rsi"]) == 100 and c["ema20"][-1] is not None
    assert client.get(f"{API}/markets/NOPE", headers=user["h"]).status_code == 404
    assert client.get(f"{API}/markets/status").json()["simulated"] is True


def test_watchlists(client, user):
    h = user["h"]
    w = client.post(f"{API}/watchlists", headers=h, json={"name": "Banks"}).json()
    r = client.post(f"{API}/watchlists/{w['id']}/items", headers=h, json={"symbol": "sbin"})
    assert r.status_code == 201 and r.json()["items"][0]["symbol"] == "SBIN"
    assert client.post(f"{API}/watchlists/{w['id']}/items", headers=h, json={"symbol": "SBIN"}).status_code == 409
    assert client.delete(f"{API}/watchlists/{w['id']}/items/SBIN", headers=h).json()["items"] == []
    other = __import__("tests.api.conftest", fromlist=["register"]).register(client)
    assert client.get(f"{API}/watchlists", headers=other["h"]).json() == []
    assert client.delete(f"{API}/watchlists/{w['id']}", headers=other["h"]).status_code == 404


def test_market_buy_and_sell_updates_cash_position_and_pnl(client, user):
    h = user["h"]
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 100})
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["status"] == "FILLED" and o["fees"] > 0
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert pf["positions"][0]["quantity"] == 100
    assert pf["cash"] == pytest.approx(1_000_000 - 100 * o["avg_fill_price"] - o["fees"], abs=0.02)
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "SELL", "quantity": 100})
    assert r.status_code == 201
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert pf["positions"] == [] and pf["realized_pnl"] < 0  # round trip costs fees + slippage
    trades = client.get(f"{API}/trades", headers=h).json()
    assert trades["total"] == 2
    an = client.get(f"{API}/portfolio/analytics", headers=h).json()
    assert an["closed_trades"] == 1


def test_short_selling_blocked(client, user):
    r = client.post(f"{API}/orders", headers=user["h"], json={"symbol": "TCS", "side": "SELL", "quantity": 1})
    assert r.status_code == 400 and "Short selling" in r.json()["detail"]["message"]


def test_position_size_limit(client, user):
    px = price(client, user["h"], "SBIN")
    qty = int(0.25 * 1_000_000 / px)
    r = client.post(f"{API}/orders", headers=user["h"], json={"symbol": "SBIN", "side": "BUY", "quantity": qty})
    assert r.status_code == 400 and "20%" in r.json()["detail"]["message"]
    orders = client.get(f"{API}/orders?status=REJECTED", headers=user["h"]).json()
    assert orders["total"] == 1  # rejected orders are kept for the audit trail


def test_limit_order_matches_and_cancel(client, user):
    h = user["h"]
    px = price(client, h, "INFY")
    o = client.post(f"{API}/orders", headers=h, json={"symbol": "INFY", "side": "BUY", "order_type": "LIMIT",
                                                        "quantity": 10, "limit_price": round(px * 0.98, 2)}).json()
    assert o["status"] == "OPEN"
    tick("INFY", round(px * 0.97, 2))
    o2 = client.get(f"{API}/orders/{o['id']}", headers=h).json()
    assert o2["status"] == "FILLED" and o2["avg_fill_price"] <= round(px * 0.98, 2)
    o3 = client.post(f"{API}/orders", headers=h, json={"symbol": "INFY", "side": "SELL", "order_type": "LIMIT",
                                                         "quantity": 10, "limit_price": round(px * 1.5, 2)}).json()
    # open sell reserves the quantity
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "INFY", "side": "SELL", "quantity": 1})
    assert r.status_code == 400 and "reserve" in r.json()["detail"]["message"]
    assert client.post(f"{API}/orders/{o3['id']}/cancel", headers=h).json()["status"] == "CANCELLED"
    assert client.post(f"{API}/orders/{o3['id']}/cancel", headers=h).status_code == 400
    set_price("INFY", px)


def test_stop_loss_exit_on_position(client, user):
    h = user["h"]
    px = price(client, h, "LT")
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "LT", "side": "BUY", "quantity": 5,
                                                       "stop_loss": round(px * 0.95, 2), "target": round(px * 1.2, 2)})
    assert r.status_code == 201
    tick("LT", round(px * 0.94, 2))
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert all(p["symbol"] != "LT" for p in pf["positions"])
    sys_orders = client.get(f"{API}/orders?source=SYSTEM", headers=h).json()
    assert sys_orders["total"] == 1
    set_price("LT", px)


def test_daily_loss_limit_blocks_buys_not_sells(client, user):
    h = user["h"]
    client.post(f"{API}/orders", headers=h, json={"symbol": "HDFCBANK", "side": "BUY", "quantity": 10})
    with SessionLocal() as db:
        acc = db.scalar(select(Account).where(Account.user_id == user["id"]))
        acc.day_start_equity = acc.cash * 2  # pretend we lost a lot today
        db.commit()
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 1})
    assert r.status_code == 400 and "Daily loss limit" in r.json()["detail"]["message"]
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "HDFCBANK", "side": "SELL", "quantity": 10})
    assert r.status_code == 201  # exits are never blocked


def test_daily_trade_limit_only_on_buys(client, user):
    h = user["h"]
    lim = client.get(f"{API}/portfolio/risk-limits", headers=h).json()
    lim["max_daily_trades"] = 1
    assert client.put(f"{API}/portfolio/risk-limits", headers=h, json=lim).status_code == 200
    assert client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 2}).status_code == 201
    r = client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 1})
    assert r.status_code == 400 and "trade limit" in r.json()["detail"]["message"]
    assert client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "SELL", "quantity": 2}).status_code == 201


def test_concurrent_orders_cannot_overdraw(client, user):
    """8 simultaneous buys, each ~30% of cash: at most 3 can fill, cash never goes negative."""
    h = user["h"]
    lim = client.get(f"{API}/portfolio/risk-limits", headers=h).json()
    lim.update(max_position_pct=1.0, max_daily_trades=100)
    client.put(f"{API}/portfolio/risk-limits", headers=h, json=lim)
    px = price(client, h, "KOTAKBANK")
    qty = int(300_000 / px)
    with SessionLocal() as db:
        acc_id = db.scalar(select(Account.id).where(Account.user_id == user["id"]))
    results = []

    def worker():
        with SessionLocal() as db:
            inst = db.scalar(select(Instrument).where(Instrument.symbol == "KOTAKBANK"))
            try:
                broker.place_order(db, acc_id, inst, "BUY", "MARKET", qty)
                results.append("ok")
            except broker.OrderRejected:
                results.append("rej")

    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("ok") == 3
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert pf["cash"] >= 0 and pf["positions"][0]["quantity"] == 3 * qty


def test_alert_triggers_notification(client, user):
    h = user["h"]
    px = price(client, h, "AXISBANK")
    assert client.post(f"{API}/alerts", headers=h, json={"symbol": "AXISBANK", "condition": "ABOVE",
                                                          "price": round(px * 0.9, 2)}).status_code == 400
    a = client.post(f"{API}/alerts", headers=h, json={"symbol": "AXISBANK", "condition": "ABOVE",
                                                       "price": round(px * 1.05, 2), "note": "breakout"}).json()
    tick("AXISBANK", round(px * 1.06, 2))
    assert client.get(f"{API}/alerts", headers=h).json()[0]["is_active"] is False
    n = client.get(f"{API}/notifications", headers=h).json()
    assert n["unread"] >= 1 and any(x["kind"] == "PRICE_ALERT" for x in n["items"])
    client.post(f"{API}/notifications/read-all", headers=h)
    assert client.get(f"{API}/notifications", headers=h).json()["unread"] == 0
    set_price("AXISBANK", px)
    assert a["id"]


def test_dashboard_and_reset(client, user):
    h = user["h"]
    client.post(f"{API}/orders", headers=h, json={"symbol": "ITC", "side": "BUY", "quantity": 3})
    d = client.get(f"{API}/dashboard", headers=h).json()
    assert {c["key"]: c["done"] for c in d["checklist"]}["order"] is True
    assert client.post(f"{API}/portfolio/reset", headers=h, json={"confirm": True}).status_code == 200
    pf = client.get(f"{API}/portfolio", headers=h).json()
    assert pf["cash"] == 1_000_000 and pf["positions"] == []
