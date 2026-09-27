from datetime import date

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Candle, Instrument
from scripts import corporate_actions, import_bhavcopy

LEGACY = """SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,
ZZTEST,EQ,100,110,95,105,105,99,1000,105000,01-JAN-2024,10,INE000,
ZZTEST,BE,1,1,1,1,1,1,1,1,01-JAN-2024,1,INE000,
ZZBAD,EQ,100,90,95,105,105,99,1000,105000,01-JAN-2024,10,INE001,
"""
UDIFF = """TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
2024-01-02,2024-01-02,CM,NSE,STK,1,INE000,ZZTEST,EQ,,,,,ZZ Test Ltd,106,112,104,110,110,105,,110,,,2000,220000,20,F1,1,,,,,
2024-01-03,2024-01-03,CM,NSE,STK,1,INE000,ZZTEST,EQ,,,,,ZZ Test Ltd,110,115,108,112,112,110,,112,,,1500,168000,15,F1,1,,,,,
"""


def test_bhavcopy_legacy_and_udiff_and_split(tmp_path, client):
    (tmp_path / "legacy.csv").write_text(LEGACY)
    (tmp_path / "udiff.csv").write_text(UDIFF)
    df = import_bhavcopy.parse_files([tmp_path / "legacy.csv", tmp_path / "udiff.csv"], {"EQ"}, None)
    assert list(df["symbol"].unique()) == ["ZZTEST"]  # BE series and the invalid OHLC row are dropped
    assert len(df) == 3
    with SessionLocal() as db:
        stats = import_bhavcopy.import_frame(db, df)
        assert stats == {"symbols": 1, "candles": 3, "replaced_simulated": 0}
        assert import_bhavcopy.import_frame(db, df)["candles"] == 0  # idempotent
        inst = db.scalar(select(Instrument).where(Instrument.symbol == "ZZTEST"))
        assert inst.data_source == "NSE_BHAVCOPY" and inst.last_price == 112 and inst.name == "ZZ Test Ltd"
        r = corporate_actions.apply(db, "ZZTEST", date(2024, 1, 3), corporate_actions.factor_from("10:2", None))
        assert r["candles"] == 2
        closes = db.scalars(select(Candle.close).where(Candle.instrument_id == inst.id).order_by(Candle.ts)).all()
        assert closes == pytest.approx([21.0, 22.0, 112.0])


def test_corporate_action_factor():
    assert corporate_actions.factor_from(None, "1:1") == 2.0
    assert corporate_actions.factor_from("10:1", None) == 10.0
    with pytest.raises(ValueError):
        corporate_actions.factor_from("1:1", "1:1")
