"""Tests for universe filtering."""

from __future__ import annotations

from src.config.settings import ExclusionsConfig, UniverseConfig
from src.strategy.universe_filter import filter_candidate


def _default_universe() -> UniverseConfig:
    return UniverseConfig()


def _default_exclusions() -> ExclusionsConfig:
    return ExclusionsConfig()


class TestUniverseFilter:
    def test_passes_all(self):
        result = filter_candidate(
            ticker="AAPL",
            price=150.0,
            avg_daily_volume=5_000_000,
            premarket_volume=200_000,
            premarket_dollar_volume=10_000_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is True
        assert result.rejection_reasons == []

    def test_rejects_low_price(self):
        result = filter_candidate(
            ticker="PENNY",
            price=5.0,
            avg_daily_volume=5_000_000,
            premarket_volume=200_000,
            premarket_dollar_volume=10_000_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False
        assert any("price" in r for r in result.rejection_reasons)

    def test_rejects_low_volume(self):
        result = filter_candidate(
            ticker="THINLY",
            price=50.0,
            avg_daily_volume=100_000,
            premarket_volume=200_000,
            premarket_dollar_volume=10_000_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False
        assert any("avg_daily_vol" in r for r in result.rejection_reasons)

    def test_rejects_low_premarket_volume(self):
        result = filter_candidate(
            ticker="QUIET",
            price=50.0,
            avg_daily_volume=5_000_000,
            premarket_volume=10_000,
            premarket_dollar_volume=10_000_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False

    def test_rejects_low_premarket_dollar_volume(self):
        result = filter_candidate(
            ticker="CHEAP",
            price=50.0,
            avg_daily_volume=5_000_000,
            premarket_volume=200_000,
            premarket_dollar_volume=500_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False

    def test_rejects_otc(self):
        result = filter_candidate(
            ticker="OTCBB",
            price=50.0,
            avg_daily_volume=5_000_000,
            premarket_volume=200_000,
            premarket_dollar_volume=10_000_000,
            is_otc=True,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False
        assert any("OTC" in r for r in result.rejection_reasons)

    def test_rejects_excluded_ticker(self):
        exclusions = ExclusionsConfig(excluded_tickers=["BAD"])
        result = filter_candidate(
            ticker="BAD",
            price=50.0,
            avg_daily_volume=5_000_000,
            premarket_volume=200_000,
            premarket_dollar_volume=10_000_000,
            is_otc=False,
            universe=_default_universe(),
            exclusions=exclusions,
        )
        assert result.eligible is False
        assert any("exclusion" in r for r in result.rejection_reasons)

    def test_multiple_rejections(self):
        result = filter_candidate(
            ticker="FAIL",
            price=3.0,
            avg_daily_volume=50_000,
            premarket_volume=5_000,
            premarket_dollar_volume=10_000,
            is_otc=True,
            universe=_default_universe(),
            exclusions=_default_exclusions(),
        )
        assert result.eligible is False
        assert len(result.rejection_reasons) >= 4
