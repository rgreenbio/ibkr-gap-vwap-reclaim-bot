"""Order construction helpers for the gap-down VWAP reclaim strategy."""

from __future__ import annotations


def build_bracket_order(
    qty: int,
    entry_price: float,
    target_price: float,
    stop_price: float,
):
    """Build a bracket order: limit buy entry + take-profit limit sell + stop-loss sell.

    Returns (parent, take_profit, stop_loss) tuple.
    """
    from ib_insync import IB
    return IB.bracketOrder(
        action="BUY",
        quantity=qty,
        limitPrice=entry_price,
        takeProfitPrice=target_price,
        stopLossPrice=stop_price,
    )


def build_flatten_order(qty: int):
    """Market sell to flatten a position at end of day."""
    from ib_insync import MarketOrder
    return MarketOrder("SELL", qty)
