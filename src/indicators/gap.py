"""Gap percentage calculation."""

from __future__ import annotations


def compute_gap_pct(current_price: float, prior_close: float) -> float:
    """Compute gap percentage. Negative = gap down."""
    if prior_close == 0:
        return 0.0
    return round((current_price - prior_close) / prior_close * 100, 4)


def is_gap_down(gap_pct: float, threshold: float = 5.0) -> bool:
    """True if the gap down is at least as large as threshold (positive number)."""
    return gap_pct <= -abs(threshold)
