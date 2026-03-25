"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.config.settings import (
    AppConfig,
    ExclusionsConfig,
    RiskConfig,
    ScheduleConfig,
    StrategyConfig,
    StretchConfig,
    StopConfig,
    TargetConfig,
    UniverseConfig,
)
from src.storage.db import init_db


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


@pytest.fixture
def sample_config() -> AppConfig:
    return AppConfig(
        strategy=StrategyConfig(
            stretch=StretchConfig(rsi_period=5, rsi_max=25, min_distance_below_vwap_pct=0.5),
            stop=StopConfig(buffer_pct=0.1),
            target=TargetConfig(r_multiple=2.0),
        ),
        universe=UniverseConfig(),
        risk=RiskConfig(),
        schedule=ScheduleConfig(),
        exclusions=ExclusionsConfig(),
    )


def make_bars_df(
    n: int = 20,
    start_price: float = 50.0,
    trend: float = -0.5,
    volume_base: int = 100_000,
    ticker: str = "TEST",
) -> pd.DataFrame:
    """Generate synthetic 1-minute OHLCV bars.

    trend: per-bar price drift (negative = downward).
    """
    np.random.seed(42)
    closes = [start_price]
    for i in range(1, n):
        change = trend + np.random.normal(0, 0.2)
        closes.append(round(closes[-1] + change, 2))

    closes = np.array(closes)
    highs = closes + np.abs(np.random.normal(0.1, 0.05, n))
    lows = closes - np.abs(np.random.normal(0.1, 0.05, n))
    opens = np.roll(closes, 1)
    opens[0] = start_price
    volumes = np.random.randint(volume_base // 2, volume_base * 2, size=n)

    idx = pd.date_range("2026-03-20 09:30", periods=n, freq="1min", tz="America/New_York")

    df = pd.DataFrame({
        "open": np.round(opens, 2),
        "high": np.round(highs, 2),
        "low": np.round(lows, 2),
        "close": np.round(closes, 2),
        "volume": volumes,
    }, index=idx)
    df.attrs["ticker"] = ticker
    return df
