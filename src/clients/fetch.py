"""Data fetching from TWS: snapshots, historical bars, volume data."""

from __future__ import annotations

import logging
import math
from zoneinfo import ZoneInfo

import pandas as pd

from src.clients.contracts import stock_contract

logger = logging.getLogger("gap_vwap_bot.fetch")

PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")


def _safe_val(val):
    """Return None for missing/invalid TWS values (nan, -1, None)."""
    if val is None:
        return None
    try:
        if math.isnan(val):
            return None
    except TypeError:
        pass
    if val == -1.0:
        return None
    return val


def get_snapshot(ib, ticker: str) -> dict:
    """Get a market data snapshot for a stock ticker."""
    contract = stock_contract(ticker)
    ib.qualifyContracts(contract)
    ib.sleep(0.5)
    [ticker_data] = ib.reqTickers(contract)

    is_delayed = getattr(ticker_data, "marketDataType", 1) in (2, 3)

    last = _safe_val(getattr(ticker_data, "last", None))
    close = _safe_val(getattr(ticker_data, "close", None))
    if last is None:
        mp = getattr(ticker_data, "marketPrice", None)
        last = _safe_val(mp() if callable(mp) else mp)
    if last is None:
        last = close

    return {
        "ticker": ticker,
        "bid": _safe_val(getattr(ticker_data, "bid", None)),
        "ask": _safe_val(getattr(ticker_data, "ask", None)),
        "last": last,
        "close": close,
        "high": _safe_val(getattr(ticker_data, "high", None)),
        "low": _safe_val(getattr(ticker_data, "low", None)),
        "volume": _safe_val(getattr(ticker_data, "volume", None)),
        "delayed": is_delayed,
    }


def get_historical_bars_1min(
    ib,
    ticker: str,
    duration: str = "1 D",
    use_rth: bool = False,
) -> pd.DataFrame | None:
    """Fetch 1-minute OHLCV bars from TWS. Includes premarket if use_rth=False."""
    from ib_insync import util

    contract = stock_contract(ticker)
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=use_rth,
        formatDate=1,
    )
    if not bars:
        return None
    df = util.df(bars)
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is None:
        try:
            df["date"] = df["date"].dt.tz_localize(ET)
        except Exception:
            pass
    else:
        df["date"] = df["date"].dt.tz_convert(ET)
    df = df.sort_values("date").reset_index(drop=True)
    df.attrs["ticker"] = ticker
    return df


def get_prior_close(ib, ticker: str) -> float | None:
    """Get previous session's closing price."""
    from ib_insync import util

    contract = stock_contract(ticker)
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr="2 D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
    )
    if not bars or len(bars) < 2:
        return None
    return bars[-2].close


def get_avg_daily_volume(ib, ticker: str, days: int = 10) -> float | None:
    """Average daily volume over last N complete sessions."""
    from ib_insync import util

    contract = stock_contract(ticker)
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=f"{days + 2} D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
    )
    if not bars:
        return None
    df = util.df(bars)
    # Exclude today (last row may be incomplete)
    df = df.iloc[-(days + 1):-1]
    return df["volume"].mean() if not df.empty else None


def get_premarket_data(ib, ticker: str) -> dict:
    """Get today's premarket volume and dollar volume from 1-min bars."""
    df = get_historical_bars_1min(ib, ticker, duration="1 D", use_rth=False)
    if df is None or df.empty:
        return {"premarket_volume": 0, "premarket_dollar_volume": 0}

    # Premarket = before 9:30 ET today
    today = pd.Timestamp.now(tz=ET).normalize()
    market_open = today.replace(hour=9, minute=30)
    premarket = df[df["date"] < market_open]

    if premarket.empty:
        return {"premarket_volume": 0, "premarket_dollar_volume": 0}

    vol = premarket["volume"].sum()
    typical = (premarket["high"] + premarket["low"] + premarket["close"]) / 3
    dollar_vol = (typical * premarket["volume"]).sum()

    return {
        "premarket_volume": vol,
        "premarket_dollar_volume": dollar_vol,
    }
