import time as _time
from datetime import date, datetime

import pytest

from app.bots.bot_sandbox import run_sandboxed, SandboxLimits, SandboxTimeout, SandboxError
from app.bots.market_calendar import ExchangeCalendar, IST
from app.strategies.engine.strategy_engine import evaluate


def _slow():
    _time.sleep(5)


def _boom():
    raise RuntimeError("strategy bug")


def _hog():
    return bytearray(4 * 1024 ** 3)   # 4 GB


def test_sandbox_returns_real_evaluation(ohlcv):
    out = run_sandboxed(evaluate, ohlcv)
    assert out["algorithm_version"] == "1.2"
    assert out["action"] in {"BUY", "HOLD"}


def test_sandbox_timeout():
    with pytest.raises(SandboxTimeout):
        run_sandboxed(_slow, limits=SandboxLimits(wall_timeout_s=0.5))


def test_sandbox_propagates_errors():
    with pytest.raises(SandboxError, match="strategy bug"):
        run_sandboxed(_boom)


def test_sandbox_memory_limit():
    with pytest.raises(SandboxError):
        run_sandboxed(_hog, limits=SandboxLimits(memory_mb=1024))


def test_market_hours():
    cal = ExchangeCalendar(holidays={date(2026, 10, 2)})
    assert cal.is_open(datetime(2026, 9, 28, 10, 0, tzinfo=IST))        # Monday
    assert not cal.is_open(datetime(2026, 9, 28, 9, 0, tzinfo=IST))     # pre-open
    assert not cal.is_open(datetime(2026, 9, 28, 15, 30, tzinfo=IST))   # close is exclusive
    assert not cal.is_open(datetime(2026, 9, 27, 11, 0, tzinfo=IST))    # Sunday
    assert not cal.is_open(datetime(2026, 10, 2, 11, 0, tzinfo=IST))    # holiday
    with pytest.raises(ValueError):
        cal.is_open(datetime(2026, 9, 28, 10, 0))
