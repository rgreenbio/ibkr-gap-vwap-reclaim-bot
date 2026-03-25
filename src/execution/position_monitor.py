"""Position monitoring: detect fills, target hits, stop hits, and time exits."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.contracts import stock_contract
from src.config.settings import AppConfig
from src.execution.order_builder import build_flatten_order
from src.execution.order_submit import cancel_all_for_ticker, submit_flatten
from src.models.domain import PaperTrade, TradeState
from src.storage.repositories import update_trade_state

logger = logging.getLogger("gap_vwap_bot.monitor")

PT = ZoneInfo("America/Los_Angeles")


def check_flatten_deadline(config: AppConfig) -> bool:
    """Return True if current time is at or past the flatten deadline."""
    now = datetime.now(PT)
    h, m = map(int, config.schedule.flatten_time_pt.split(":"))
    deadline = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return now >= deadline


def monitor_filled_position(
    ib,
    trade: PaperTrade,
    conn: sqlite3.Connection,
    config: AppConfig,
) -> None:
    """Check a filled position for exit conditions.

    Looks at IBKR order statuses to detect target hit (TP fill) or stop hit (SL fill).
    Also checks the flatten deadline for time exit.
    """
    if trade.state != TradeState.PAPER_ORDER_FILLED:
        return

    # Check flatten deadline first — highest priority
    if check_flatten_deadline(config):
        logger.info(f"{trade.ticker}: flatten deadline reached, forcing exit")
        _execute_time_exit(ib, trade, conn)
        return

    # Check IBKR order statuses for bracket legs
    for ibkr_trade in ib.openTrades():
        if getattr(ibkr_trade.contract, "symbol", "") != trade.ticker:
            continue

        status = ibkr_trade.orderStatus.status
        order_type = getattr(ibkr_trade.order, "orderType", "")

        if status == "Filled":
            if order_type == "LMT" and ibkr_trade.order.action == "SELL":
                # Take profit hit
                fill_price = ibkr_trade.orderStatus.avgFillPrice
                logger.info(f"{trade.ticker}: TARGET HIT at {fill_price}")
                update_trade_state(
                    conn, trade.trade_id, TradeState.TARGET_HIT,
                    exit_price=fill_price,
                    exit_time=datetime.now(PT),
                    exit_reason="target_hit",
                )
                _finalize_trade(conn, trade.trade_id, fill_price, trade)
                return

            if order_type == "STP":
                # Stop loss hit
                fill_price = ibkr_trade.orderStatus.avgFillPrice
                logger.info(f"{trade.ticker}: STOP HIT at {fill_price}")
                update_trade_state(
                    conn, trade.trade_id, TradeState.STOP_HIT,
                    exit_price=fill_price,
                    exit_time=datetime.now(PT),
                    exit_reason="stop_hit",
                )
                _finalize_trade(conn, trade.trade_id, fill_price, trade)
                return

    # Update MFE/MAE tracking
    _update_excursions(ib, trade, conn)


def _execute_time_exit(ib, trade: PaperTrade, conn: sqlite3.Connection) -> None:
    """Cancel bracket legs and market sell to flatten."""
    cancel_all_for_ticker(ib, trade.ticker)

    contract = stock_contract(trade.ticker)
    ib.qualifyContracts(contract)
    flatten_order = build_flatten_order(trade.shares)
    result = submit_flatten(ib, contract, flatten_order)

    fill_price = result.orderStatus.avgFillPrice if result.orderStatus else None

    update_trade_state(
        conn, trade.trade_id, TradeState.TIME_EXIT,
        exit_price=fill_price,
        exit_time=datetime.now(PT),
        exit_reason="time_exit",
    )
    _finalize_trade(conn, trade.trade_id, fill_price, trade)


def _finalize_trade(
    conn: sqlite3.Connection,
    trade_id: str,
    exit_price: float | None,
    trade: PaperTrade,
) -> None:
    """Compute PnL and close the trade."""
    pnl = None
    pnl_pct = None
    if exit_price and trade.fill_price and trade.shares:
        pnl = round((exit_price - trade.fill_price) * trade.shares, 2)
        pnl_pct = round((exit_price - trade.fill_price) / trade.fill_price * 100, 2)

    update_trade_state(
        conn, trade_id, TradeState.CLOSED,
        pnl_dollars=pnl,
        pnl_pct=pnl_pct,
    )
    logger.info(f"{trade.ticker}: trade CLOSED — PnL: ${pnl}")


def _update_excursions(ib, trade: PaperTrade, conn: sqlite3.Connection) -> None:
    """Track maximum favorable and adverse excursion."""
    if not trade.fill_price:
        return

    from src.clients.fetch import get_snapshot
    snap = get_snapshot(ib, trade.ticker)
    current = snap.get("last")
    if current is None:
        return

    mfe = trade.max_favorable_excursion or 0.0
    mae = trade.max_adverse_excursion or 0.0

    excursion = current - trade.fill_price
    new_mfe = max(mfe, excursion)
    new_mae = min(mae, excursion)

    if new_mfe != mfe or new_mae != mae:
        conn.execute(
            "UPDATE trades SET max_favorable_excursion=?, max_adverse_excursion=? WHERE trade_id=?",
            (new_mfe, new_mae, trade.trade_id),
        )
        conn.commit()
