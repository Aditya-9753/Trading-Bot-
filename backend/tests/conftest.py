import os
import sys
import tempfile

# API tests: isolated SQLite file, no background simulator, small history.
_TMP = tempfile.mkdtemp(prefix="tradebot-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("ENABLE_SIMULATOR", "false")
os.environ.setdefault("HISTORY_BARS", "400")
os.environ.setdefault("TICKS_PER_BAR", "4")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.synthetic_data import make_ohlcv  # noqa: E402


@pytest.fixture
def ohlcv():
    return make_ohlcv(n=900, seed=7)
