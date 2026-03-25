"""Contract creation helpers."""

from __future__ import annotations


def stock_contract(ticker: str):
    """Create a US stock contract routed via SMART."""
    from ib_insync import Stock
    return Stock(ticker, "SMART", "USD")
