"""Tests for indicator calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.indicators.gap import compute_gap_pct, is_gap_down
from src.indicators.rsi import compute_rsi, compute_rsi_series
from src.indicators.vwap import compute_vwap, vwap_distance_pct
from tests.conftest import make_bars_df


class TestGap:
    def test_gap_down(self):
        assert compute_gap_pct(95.0, 100.0) == -5.0

    def test_gap_up(self):
        assert compute_gap_pct(105.0, 100.0) == 5.0

    def test_no_gap(self):
        assert compute_gap_pct(100.0, 100.0) == 0.0

    def test_zero_prior_close(self):
        assert compute_gap_pct(50.0, 0.0) == 0.0

    def test_is_gap_down_true(self):
        assert is_gap_down(-5.0, 5.0) is True
        assert is_gap_down(-7.5, 5.0) is True

    def test_is_gap_down_false(self):
        assert is_gap_down(-4.9, 5.0) is False
        assert is_gap_down(5.0, 5.0) is False

    def test_is_gap_down_exact_threshold(self):
        assert is_gap_down(-5.0, 5.0) is True


class TestRSI:
    def test_insufficient_data(self):
        closes = pd.Series([100.0, 101.0, 102.0])
        assert compute_rsi(closes, period=5) is None

    def test_all_gains(self):
        closes = pd.Series([100.0 + i for i in range(10)])
        rsi = compute_rsi(closes, period=5)
        assert rsi == 100.0

    def test_all_losses(self):
        closes = pd.Series([100.0 - i for i in range(10)])
        rsi = compute_rsi(closes, period=5)
        assert rsi is not None
        assert rsi < 5.0

    def test_mixed_movement(self):
        closes = pd.Series([100, 102, 101, 103, 99, 100, 98, 97, 96, 95])
        rsi = compute_rsi(closes, period=5)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_series_length(self):
        closes = pd.Series([100.0 + np.sin(i) for i in range(30)])
        series = compute_rsi_series(closes, period=5)
        assert len(series) == len(closes)

    def test_none_input(self):
        assert compute_rsi(None, period=5) is None


class TestVWAP:
    def test_basic_vwap(self):
        bars = pd.DataFrame({
            "high": [10.2, 10.5, 10.3],
            "low": [9.8, 10.0, 10.0],
            "close": [10.0, 10.2, 10.1],
            "volume": [1000, 2000, 1500],
        })
        vwap = compute_vwap(bars)
        assert len(vwap) == 3
        # First bar VWAP = typical price of first bar
        tp0 = (10.2 + 9.8 + 10.0) / 3
        assert abs(vwap.iloc[0] - tp0) < 0.001

    def test_vwap_zero_volume(self):
        bars = pd.DataFrame({
            "high": [10.0], "low": [10.0], "close": [10.0], "volume": [0],
        })
        vwap = compute_vwap(bars)
        assert pd.isna(vwap.iloc[0])

    def test_distance_below(self):
        dist = vwap_distance_pct(95.0, 100.0)
        assert dist == -5.0

    def test_distance_above(self):
        dist = vwap_distance_pct(105.0, 100.0)
        assert dist == 5.0

    def test_distance_zero_vwap(self):
        assert vwap_distance_pct(50.0, 0.0) == 0.0

    def test_vwap_with_synthetic_bars(self):
        bars = make_bars_df(n=20, start_price=50.0, trend=-0.3)
        vwap = compute_vwap(bars)
        assert len(vwap) == 20
        assert not vwap.isna().all()
