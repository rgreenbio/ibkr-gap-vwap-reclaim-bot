"""Order submission with safety checks and JSON logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.clients.safety import assert_paper_trading

logger = logging.getLogger("gap_vwap_bot.orders")

PT = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _order_log_dir() -> Path:
    today = datetime.now(PT).strftime("%Y-%m-%d")
    d = PROJECT_ROOT / "outputs" / "orders" / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_order(contract, order, trade=None, status="PendingSubmit") -> Path:
    now = datetime.now(PT)
    symbol = getattr(contract, "symbol", "UNKNOWN")
    action = getattr(order, "action", "UNKNOWN")

    filename = f"{now.strftime('%H%M%S')}_{symbol}_{action}.json"
    path = _order_log_dir() / filename

    counter = 1
    while path.exists():
        filename = f"{now.strftime('%H%M%S')}_{symbol}_{action}_{counter}.json"
        path = _order_log_dir() / filename
        counter += 1

    log_data = {
        "timestamp": now.isoformat(),
        "symbol": symbol,
        "action": action,
        "order_type": getattr(order, "orderType", "UNKNOWN"),
        "quantity": getattr(order, "totalQuantity", 0),
        "limit_price": getattr(order, "lmtPrice", None),
        "stop_price": getattr(order, "auxPrice", None),
        "status": status,
        "paper_trading": True,
    }

    if trade and trade.orderStatus:
        log_data["status"] = trade.orderStatus.status
        log_data["fill_price"] = trade.orderStatus.avgFillPrice or None
    if trade and trade.fills:
        total_comm = sum(
            f.commissionReport.commission for f in trade.fills
            if f.commissionReport.commission < 1e9
        )
        log_data["commission"] = total_comm if total_comm > 0 else None

    with open(path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, default=str)

    logger.info(f"Order logged: {path}")
    return path


def submit_bracket(ib, contract, bracket) -> list:
    """Submit a bracket order (parent + take profit + stop loss). Paper-trading only."""
    assert_paper_trading(ib)

    trades = []
    for order in bracket:
        trade = ib.placeOrder(contract, order)
        trades.append(trade)

    ib.sleep(1)

    for trade in trades:
        _log_order(contract, trade.order, trade, trade.orderStatus.status)

    logger.info(f"Bracket order submitted: {len(trades)} legs")
    return trades


def submit_flatten(ib, contract, order) -> object:
    """Submit a market sell to flatten a position. Paper-trading only."""
    assert_paper_trading(ib)

    logger.info(f"Flattening position: SELL {order.totalQuantity} {contract.symbol}")
    trade = ib.placeOrder(contract, order)
    ib.sleep(1)
    _log_order(contract, order, trade, trade.orderStatus.status)
    return trade


def cancel_all_for_ticker(ib, ticker: str) -> int:
    """Cancel all open orders for a given ticker. Returns count cancelled."""
    assert_paper_trading(ib)
    cancelled = 0
    for trade in ib.openTrades():
        if getattr(trade.contract, "symbol", "") == ticker:
            ib.cancelOrder(trade.order)
            cancelled += 1
    if cancelled:
        ib.sleep(1)
        logger.info(f"Cancelled {cancelled} open orders for {ticker}")
    return cancelled
