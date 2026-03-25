"""RSI (Relative Strength Index) — Wilder's smoothing method."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(closes: pd.Series, period: int = 5) -> float | None:
    """Return the most recent RSI value, or None if insufficient data."""
    if closes is None or len(closes) < period + 1:
        return None

    deltas = closes.diff()
    gains = deltas.clip(lower=0)
    losses = (-deltas).clip(lower=0)

    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    last_avg_loss = avg_loss.iloc[-1]
    if last_avg_loss == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / last_avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def compute_rsi_series(closes: pd.Series, period: int = 5) -> pd.Series:
    """Return RSI as a full series aligned with the input."""
    deltas = closes.diff()
    gains = deltas.clip(lower=0)
    losses = (-deltas).clip(lower=0)

    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)
