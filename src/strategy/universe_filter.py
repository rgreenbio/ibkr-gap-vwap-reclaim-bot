"""Universe filtering — determines whether a candidate passes eligibility rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.settings import UniverseConfig, ExclusionsConfig


@dataclass
class FilterResult:
    ticker: str
    eligible: bool = True
    rejection_reasons: list[str] = field(default_factory=list)

    def reject(self, reason: str) -> None:
        self.eligible = False
        self.rejection_reasons.append(reason)


def filter_candidate(
    ticker: str,
    price: float,
    avg_daily_volume: float,
    premarket_volume: float,
    premarket_dollar_volume: float,
    is_otc: bool,
    universe: UniverseConfig,
    exclusions: ExclusionsConfig,
) -> FilterResult:
    """Apply all universe filters to a single candidate."""
    result = FilterResult(ticker=ticker)

    if price < universe.min_price:
        result.reject(f"price {price:.2f} < min {universe.min_price}")

    if avg_daily_volume < universe.min_avg_daily_volume:
        result.reject(
            f"avg_daily_vol {avg_daily_volume:,.0f} < min {universe.min_avg_daily_volume:,}"
        )

    if premarket_volume < universe.min_premarket_volume:
        result.reject(
            f"premarket_vol {premarket_volume:,.0f} < min {universe.min_premarket_volume:,}"
        )

    if premarket_dollar_volume < universe.min_premarket_dollar_volume:
        result.reject(
            f"premarket_dollar_vol ${premarket_dollar_volume:,.0f} "
            f"< min ${universe.min_premarket_dollar_volume:,}"
        )

    if is_otc and universe.exclude_otc:
        result.reject("OTC stock excluded")

    if ticker.upper() in [t.upper() for t in exclusions.excluded_tickers]:
        result.reject("ticker in exclusion list")

    if exclusions.exclude_leveraged_etfs:
        if ticker.upper() in [t.upper() for t in exclusions.leveraged_etf_patterns]:
            result.reject("leveraged/inverse ETF excluded")

    return result
