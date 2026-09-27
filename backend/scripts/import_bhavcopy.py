"""Import NSE equity bhav copies (daily OHLCV for all symbols) into the candles table.

Supports both formats NSE has published:
  * legacy  cmDDMMMYYYYbhav.csv(.zip): SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, TIMESTAMP
  * UDiFF   BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv(.zip): TradDt, TckrSymb, SctySrs, OpnPric, HghPric,
            LwPric, ClsPric, TtlTradgVol, FinInstrmNm
Download them from the NSE website (All Reports -> Equities). Prices in bhav copies are NOT adjusted
for splits/bonuses: run scripts/corporate_actions.py afterwards for every such event.

Usage:
  python -m scripts.import_bhavcopy path/to/files/*.csv [*.zip] [--symbols RELIANCE,TCS] [--series EQ,BE]
If an instrument currently holds SIMULATED history, that history is deleted first (real and synthetic
data are never mixed in one series).
"""
import argparse
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd

LEGACY = {"SYMBOL": "symbol", "SERIES": "series", "OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close",
          "TOTTRDQTY": "volume", "TIMESTAMP": "date"}
UDIFF = {"TckrSymb": "symbol", "SctySrs": "series", "OpnPric": "open", "HghPric": "high", "LwPric": "low",
         "ClsPric": "close", "TtlTradgVol": "volume", "TradDt": "date", "FinInstrmNm": "name"}


def _read_any(path: Path) -> list[pd.DataFrame]:
    if path.suffix.lower() == ".zip":
        out = []
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    out.append(pd.read_csv(io.BytesIO(z.read(n))))
        return out
    return [pd.read_csv(path)]


def normalise(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.rename(columns=lambda c: str(c).strip())
    if "TckrSymb" in raw.columns:
        df = raw[[c for c in UDIFF if c in raw.columns]].rename(columns=UDIFF)
        df["date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y-%m-%d")
    elif "SYMBOL" in raw.columns:
        df = raw[list(LEGACY)].rename(columns=LEGACY)
        df["date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%d-%b-%Y")
    else:
        raise ValueError("unrecognised bhav copy format (expected legacy or UDiFF columns)")
    if "name" not in df.columns:
        df["name"] = df["symbol"]
    for c in ("symbol", "series", "name"):
        df[c] = df[c].astype(str).str.strip()
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    bad = (df["high"] < df[["open", "close", "low"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))
    return df[~bad & (df["close"] > 0)].reset_index(drop=True)


def parse_files(paths: list[Path], series: set[str], symbols: set[str] | None) -> pd.DataFrame:
    frames = [normalise(r) for p in paths for r in _read_any(p)]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df[df["series"].isin(series)]
    if symbols:
        df = df[df["symbol"].isin(symbols)]
    return df.drop_duplicates(["symbol", "date"], keep="last").sort_values(["symbol", "date"])


def import_frame(db, df: pd.DataFrame) -> dict:
    from sqlalchemy import delete, select
    from app.models import Candle, Instrument
    from app.services.market_data import insert_candles, refresh_last_price
    stats = {"symbols": 0, "candles": 0, "replaced_simulated": 0}
    for sym, g in df.groupby("symbol"):
        inst = db.scalar(select(Instrument).where(Instrument.symbol == sym))
        if inst is None:
            inst = Instrument(symbol=sym, name=g["name"].iloc[-1][:160], data_source="NSE_BHAVCOPY")
            db.add(inst)
            db.flush()
        elif inst.data_source == "SIMULATED":
            db.execute(delete(Candle).where(Candle.instrument_id == inst.id))
            inst.data_source = "NSE_BHAVCOPY"
            stats["replaced_simulated"] += 1
        frame = g.set_index("date")[["open", "high", "low", "close", "volume"]]
        stats["candles"] += insert_candles(db, inst, frame, "NSE")
        db.flush()
        refresh_last_price(db, inst)
        stats["symbols"] += 1
    db.commit()
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--symbols", default="", help="comma-separated whitelist, e.g. RELIANCE,TCS")
    ap.add_argument("--series", default="EQ", help="series to keep (default EQ)")
    a = ap.parse_args(argv)
    from app.core.db import Base, SessionLocal, engine
    Base.metadata.create_all(engine)
    df = parse_files(a.files, set(a.series.split(",")), set(a.symbols.split(",")) if a.symbols else None)
    if df.empty:
        print("nothing to import")
        return 1
    with SessionLocal() as db:
        stats = import_frame(db, df)
    print(f"imported {stats['candles']} candles for {stats['symbols']} symbols "
          f"({df['date'].min().date()} .. {df['date'].max().date()}); "
          f"replaced simulated history for {stats['replaced_simulated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
