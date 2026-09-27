"""Candle storage helpers, indicator payloads for charts, and demo seeding."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Candle, Instrument, PlatformSetting, utcnow
from ..strategies.indicators import core

DEMO_UNIVERSE = [
    # ---- Indian Equities (NSE) ----
    ("RELIANCE", "Reliance Industries Ltd", "Energy", 2900, "NSE", "EQ", "EQUITY"),
    ("TCS", "Tata Consultancy Services Ltd", "IT", 3900, "NSE", "EQ", "EQUITY"),
    ("HDFCBANK", "HDFC Bank Ltd", "Banking", 1650, "NSE", "EQ", "EQUITY"),
    ("INFY", "Infosys Ltd", "IT", 1500, "NSE", "EQ", "EQUITY"),
    ("ICICIBANK", "ICICI Bank Ltd", "Banking", 1150, "NSE", "EQ", "EQUITY"),
    ("SBIN", "State Bank of India", "Banking", 780, "NSE", "EQ", "EQUITY"),
    ("ITC", "ITC Ltd", "FMCG", 440, "NSE", "EQ", "EQUITY"),
    ("LT", "Larsen & Toubro Ltd", "Infrastructure", 3500, "NSE", "EQ", "EQUITY"),
    ("BHARTIARTL", "Bharti Airtel Ltd", "Telecom", 1400, "NSE", "EQ", "EQUITY"),
    ("HINDUNILVR", "Hindustan Unilever Ltd", "FMCG", 2450, "NSE", "EQ", "EQUITY"),
    ("AXISBANK", "Axis Bank Ltd", "Banking", 1120, "NSE", "EQ", "EQUITY"),
    ("KOTAKBANK", "Kotak Mahindra Bank Ltd", "Banking", 1750, "NSE", "EQ", "EQUITY"),
    ("TATAMOTORS", "Tata Motors Ltd", "Automobile", 980, "NSE", "EQ", "EQUITY"),
    ("MARUTI", "Maruti Suzuki India Ltd", "Automobile", 12400, "NSE", "EQ", "EQUITY"),
    ("WIPRO", "Wipro Ltd", "IT", 540, "NSE", "EQ", "EQUITY"),

    # ---- Benchmark & Sectoral Indices ----
    ("NIFTY50", "NIFTY 50 Index", "Benchmark Index", 24800, "NSE", "INDEX", "INDEX"),
    ("SENSEX", "BSE SENSEX Index", "Benchmark Index", 81200, "BSE", "INDEX", "INDEX"),
    ("BANKNIFTY", "NIFTY Bank Index", "Banking Index", 52400, "NSE", "INDEX", "INDEX"),
    ("NIFTYIT", "NIFTY IT Index", "IT Index", 38600, "NSE", "INDEX", "INDEX"),
    ("NIFTYMIDCAP", "NIFTY Midcap 100", "Midcap Index", 58200, "NSE", "INDEX", "INDEX"),

    # ---- Cryptocurrencies (Priced in INR) ----
    ("BTC", "Bitcoin (BTC/INR)", "Cryptocurrency", 68500, "CRYPTO", "CRYP", "CRYPTO"),
    ("ETH", "Ethereum (ETH/INR)", "Smart Contracts", 28000, "CRYPTO", "CRYP", "CRYPTO"),
    ("SOL", "Solana (SOL/INR)", "Layer 1", 14500, "CRYPTO", "CRYP", "CRYPTO"),
    ("BNB", "Binance Coin (BNB/INR)", "Exchange Token", 48000, "CRYPTO", "CRYP", "CRYPTO"),
    ("XRP", "Ripple (XRP/INR)", "Payments", 52, "CRYPTO", "CRYP", "CRYPTO"),
    ("DOGE", "Dogecoin (DOGE/INR)", "Meme Currency", 14, "CRYPTO", "CRYP", "CRYPTO"),
    ("ADA", "Cardano (ADA/INR)", "Smart Contracts", 38, "CRYPTO", "CRYP", "CRYPTO"),
    ("AVAX", "Avalanche (AVAX/INR)", "Layer 1", 2400, "CRYPTO", "CRYP", "CRYPTO"),
]


def get_instrument(db: Session, symbol: str) -> Instrument | None:
    return db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))


def load_df(db: Session, instrument_id: int, limit: int | None = None) -> pd.DataFrame:
    q = select(Candle.ts, Candle.open, Candle.high, Candle.low, Candle.close, Candle.volume) \
        .where(Candle.instrument_id == instrument_id).order_by(Candle.ts.desc())
    if limit:
        q = q.limit(limit)
    rows = db.execute(q).all()[::-1]
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    return df.set_index(pd.DatetimeIndex(df.pop("ts"))) if len(df) else df


def _clean(v):
    if v is None:
        return None
    v = float(v)
    return None if (np.isnan(v) or np.isinf(v)) else round(v, 4)


def chart_payload(df: pd.DataFrame, bars: int) -> dict:
    """Candles plus overlays (EMA20/50) and oscillators (RSI, MACD), computed on the full series."""
    if df.empty:
        return {"candles": [], "ema20": [], "ema50": [], "rsi": [], "macd": [], "macd_signal": [], "macd_hist": []}
    close = df["close"]
    e20, e50 = core.ema(close, 20), core.ema(close, 50)
    rsi = core.rsi(close, 14)
    macd_line, sig = core.macd(close, 12, 26, 9)
    hist = macd_line - sig
    tail = slice(-bars, None)
    idx = df.index[tail]
    return {
        "candles": [{"t": t.isoformat(), "o": _clean(o), "h": _clean(h), "l": _clean(l), "c": _clean(c), "v": _clean(v)}
                    for t, o, h, l, c, v in zip(idx, df["open"].iloc[tail], df["high"].iloc[tail],
                                                df["low"].iloc[tail], close.iloc[tail], df["volume"].iloc[tail])],
        "ema20": [_clean(x) for x in e20.iloc[tail]],
        "ema50": [_clean(x) for x in e50.iloc[tail]],
        "rsi": [_clean(x) for x in rsi.iloc[tail]],
        "macd": [_clean(x) for x in macd_line.iloc[tail]],
        "macd_signal": [_clean(x) for x in sig.iloc[tail]],
        "macd_hist": [_clean(x) for x in hist.iloc[tail]],
    }


def insert_candles(db: Session, inst: Instrument, df: pd.DataFrame, source: str) -> int:
    existing = set(db.scalars(select(Candle.ts).where(Candle.instrument_id == inst.id)).all())
    n = 0
    for ts, r in df.iterrows():
        ts = pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None)
        if ts in existing:
            continue
        db.add(Candle(instrument_id=inst.id, ts=ts, open=float(r.open), high=float(r.high), low=float(r.low),
                      close=float(r.close), volume=float(r.volume), source=source))
        n += 1
    return n


def refresh_last_price(db: Session, inst: Instrument):
    last_two = db.execute(select(Candle.close).where(Candle.instrument_id == inst.id)
                          .order_by(Candle.ts.desc()).limit(2)).scalars().all()
    if last_two:
        inst.last_price = round(last_two[0], 2)
        inst.prev_close = round(last_two[1] if len(last_two) > 1 else last_two[0], 2)
        inst.updated_at = utcnow()


def seed_instruments(db: Session, bars: int) -> int:
    """Synthetic history for the demo universe. Clearly labelled SIMULATED everywhere."""
    try:
        from scripts.synthetic_data import make_ohlcv
    except ImportError:
        from backend.scripts.synthetic_data import make_ohlcv
    end = pd.Timestamp(utcnow().date()) - pd.offsets.BDay(1)
    seeded = 0
    for k, item in enumerate(DEMO_UNIVERSE):
        sym, name, sector, px = item[0], item[1], item[2], item[3]
        exch = item[4] if len(item) > 4 else "NSE"
        series = item[5] if len(item) > 5 else "EQ"
        asset_type = item[6] if len(item) > 6 else "EQUITY"
        existing = db.scalar(select(Instrument).where(Instrument.symbol == sym))
        if existing:
            if not getattr(existing, "asset_type", None) or existing.asset_type != asset_type:
                existing.asset_type = asset_type
            if not getattr(existing, "exchange", None) or existing.exchange != exch:
                existing.exchange = exch
            if not getattr(existing, "series", None) or existing.series != series:
                existing.series = series
            continue
        inst = Instrument(symbol=sym, name=name, sector=sector, exchange=exch, series=series,
                          asset_type=asset_type, data_source="SIMULATED")
        db.add(inst)
        db.flush()
        df = make_ohlcv(bars, seed=1000 + k, start_price=px)
        df.index = pd.bdate_range(end=end, periods=bars)
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].round(2)
        insert_candles(db, inst, df, "SIMULATED")
        db.flush()
        refresh_last_price(db, inst)
        seeded += 1
    return seeded


def get_setting(db: Session, key: str, default: dict) -> dict:
    s = db.get(PlatformSetting, key)
    return dict(s.value) if s else dict(default)


def set_setting(db: Session, key: str, value: dict):
    s = db.get(PlatformSetting, key)
    if s:
        s.value = value
    else:
        db.add(PlatformSetting(key=key, value=value))


def trading_halted(db: Session) -> bool:
    return bool(get_setting(db, "kill_switch", {"active": False}).get("active"))
