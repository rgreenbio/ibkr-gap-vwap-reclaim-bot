"""Core strategy logic: stretch detection, VWAP reclaim, and entry signal computation."""

from __future__ import annotations

import math

import pandas as pd

from src.config.settings import StrategyConfig, RiskConfig
from src.indicators.rsi import compute_rsi
from src.indicators.vwap import compute_vwap, vwap_distance_pct
from src.models.domain import StretchSignal, EntrySignal


def detect_stretch(
    bars: pd.DataFrame,
    config: StrategyConfig,
) -> StretchSignal | None:
    """Check if the stock is stretched/oversold based on RSI and VWAP distance.

    Requires bars with columns: open, high, low, close, volume, and a datetime index or column.
    Returns a StretchSignal if all stretch conditions are met, else None.
    """
    if len(bars) < config.stretch.rsi_period + 1:
        return None

    rsi = compute_rsi(bars["close"], period=config.stretch.rsi_period)
    if rsi is None or rsi > config.stretch.rsi_max:
        return None

    vwap_series = compute_vwap(bars)
    current_vwap = vwap_series.iloc[-1]
    current_price = bars["close"].iloc[-1]

    dist_pct = vwap_distance_pct(current_price, current_vwap)
    if dist_pct > -config.stretch.min_distance_below_vwap_pct:
        return None

    # Flush low = the lowest low seen so far in the session
    flush_low = bars["low"].min()

    return StretchSignal(
        ticker=bars.attrs.get("ticker", ""),
        rsi_value=rsi,
        vwap=round(current_vwap, 4),
        price=current_price,
        vwap_distance_pct=dist_pct,
        flush_low=flush_low,
    )


def detect_vwap_reclaim(bars: pd.DataFrame) -> bool:
    """Detect VWAP reclaim: prior completed bar closed below VWAP,
    current completed bar closes above VWAP.

    Requires at least 2 bars.
    """
    if len(bars) < 2:
        return False

    vwap_series = compute_vwap(bars)

    prev_close = bars["close"].iloc[-2]
    prev_vwap = vwap_series.iloc[-2]
    curr_close = bars["close"].iloc[-1]
    curr_vwap = vwap_series.iloc[-1]

    return bool(prev_close < prev_vwap and curr_close > curr_vwap)


def compute_entry_signal(
    ticker: str,
    entry_price: float,
    flush_low: float,
    strategy: StrategyConfig,
    risk: RiskConfig,
) -> EntrySignal | None:
    """Compute stop, target, sizing, and validate R:R.

    Returns None if the trade doesn't qualify.
    """
    buffer = flush_low * (strategy.stop.buffer_pct / 100)
    stop_price = round(flush_low - buffer, 4)

    stop_distance = entry_price - stop_price
    if stop_distance <= 0:
        return None

    # Check stop distance bounds
    stop_distance_pct = (stop_distance / entry_price) * 100
    if stop_distance_pct < risk.min_stop_distance_pct:
        return None
    if stop_distance_pct > risk.max_stop_distance_pct:
        return None

    r = stop_distance
    target_price = round(entry_price + strategy.target.r_multiple * r, 4)

    reward_risk = strategy.target.r_multiple
    if reward_risk < risk.min_reward_risk:
        return None

    shares = math.floor(risk.risk_per_trade_usd / stop_distance)
    if shares < 1:
        return None

    notional = shares * entry_price
    if notional > risk.max_position_notional_usd:
        shares = math.floor(risk.max_position_notional_usd / entry_price)
        if shares < 1:
            return None

    actual_risk = round(shares * stop_distance, 2)

    return EntrySignal(
        ticker=ticker,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        shares=shares,
        risk_dollars=actual_risk,
        reward_risk_ratio=round(reward_risk, 2),
        setup_low=flush_low,
    )
