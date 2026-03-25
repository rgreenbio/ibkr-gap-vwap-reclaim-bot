"""Trade lifecycle management: entry execution and open position management."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.contracts import stock_contract
from src.config.settings import AppConfig
from src.execution.order_builder import build_bracket_order
from src.execution.order_submit import submit_bracket
from src.execution.position_monitor import check_flatten_deadline, monitor_filled_position
from src.models.domain import EntrySignal, PaperTrade, TradeState
from src.storage.repositories import (
    get_filled_trades,
    get_open_trades,
    insert_trade,
    update_trade_state,
)

logger = logging.getLogger("gap_vwap_bot.trade_mgr")

PT = ZoneInfo("America/Los_Angeles")


def execute_entry(
    ib,
    signal: EntrySignal,
    conn: sqlite3.Connection,
    config: AppConfig,
) -> PaperTrade:
    """Place a bracket order and create a trade record."""
    today = datetime.now(PT).strftime("%Y-%m-%d")

    trade = PaperTrade(
        ticker=signal.ticker,
        state=TradeState.RISK_VALIDATED,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        target_price=signal.target_price,
        shares=signal.shares,
        risk_dollars=signal.risk_dollars,
        setup_low=signal.setup_low,
        session_date=today,
        features={
            "reward_risk_ratio": signal.reward_risk_ratio,
        },
    )

    # Transition to submitted
    trade.transition(TradeState.PAPER_ORDER_SUBMITTED)
    insert_trade(conn, trade)

    # Build and submit bracket order
    contract = stock_contract(signal.ticker)
    ib.qualifyContracts(contract)

    bracket = build_bracket_order(
        qty=signal.shares,
        entry_price=signal.entry_price,
        target_price=signal.target_price,
        stop_price=signal.stop_price,
    )

    ibkr_trades = submit_bracket(ib, contract, bracket)

    # Record IBKR order ID from parent
    if ibkr_trades:
        parent_trade = ibkr_trades[0]
        order_id = parent_trade.order.orderId
        update_trade_state(
            conn, trade.trade_id, TradeState.PAPER_ORDER_SUBMITTED,
            ibkr_order_id=order_id,
            ibkr_parent_order_id=order_id,
        )

    logger.info(
        f"{signal.ticker}: bracket order submitted — "
        f"entry={signal.entry_price}, stop={signal.stop_price}, "
        f"target={signal.target_price}, shares={signal.shares}"
    )
    return trade


def check_fills(ib, conn: sqlite3.Connection) -> None:
    """Check submitted orders for fills and update trade state."""
    trades = get_open_trades(conn)
    for trade in trades:
        if trade.state != TradeState.PAPER_ORDER_SUBMITTED:
            continue

        for ibkr_trade in ib.openTrades():
            if getattr(ibkr_trade.contract, "symbol", "") != trade.ticker:
                continue
            if ibkr_trade.orderStatus.status == "Filled":
                fill_price = ibkr_trade.orderStatus.avgFillPrice
                logger.info(f"{trade.ticker}: FILLED at {fill_price}")
                update_trade_state(
                    conn, trade.trade_id, TradeState.PAPER_ORDER_FILLED,
                    fill_price=fill_price,
                    fill_time=datetime.now(PT),
                )
                break


def manage_open_positions(ib, conn: sqlite3.Connection, config: AppConfig) -> None:
    """Monitor all filled positions for exits."""
    # First check for new fills
    check_fills(ib, conn)

    # Then monitor filled positions
    filled = get_filled_trades(conn)
    for trade in filled:
        monitor_filled_position(ib, trade, conn, config)


def flatten_all(ib, conn: sqlite3.Connection, config: AppConfig) -> None:
    """Force-flatten all open positions. Called at end of day."""
    filled = get_filled_trades(conn)
    for trade in filled:
        logger.info(f"{trade.ticker}: EOD flatten")
        from src.execution.position_monitor import _execute_time_exit
        _execute_time_exit(ib, trade, conn)
