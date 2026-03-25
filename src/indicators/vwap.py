"""VWAP (Volume Weighted Average Price) computation."""

from __future__ import annotations

import pandas as pd


def compute_vwap(bars: pd.DataFrame) -> pd.Series:
    """Compute cumulative VWAP from intraday bars.

    Expects columns: high, low, close, volume.
    Returns a Series of VWAP values aligned with the input index.
    """
    typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3
    cum_tp_vol = (typical_price * bars["volume"]).cumsum()
    cum_vol = bars["volume"].cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, float("nan"))
    return vwap


def vwap_distance_pct(price: float, vwap: float) -> float:
    """Percentage distance of price from VWAP. Negative means below VWAP."""
    if vwap == 0:
        return 0.0
    return round((price - vwap) / vwap * 100, 4)
