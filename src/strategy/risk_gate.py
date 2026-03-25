"""Risk gate — veto layer applied after strategy signal, before execution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.config.settings import RiskConfig


@dataclass
class GateResult:
    approved: bool
    reason: str

    @staticmethod
    def ok() -> GateResult:
        return GateResult(approved=True, reason="approved")

    @staticmethod
    def reject(reason: str) -> GateResult:
        return GateResult(approved=False, reason=reason)


def apply_risk_gate(
    risk_dollars: float,
    conn: sqlite3.Connection,
    config: RiskConfig,
) -> GateResult:
    """Check all risk limits. Returns GateResult.ok() or GateResult.reject(reason)."""
    from src.storage.repositories import count_open_positions, count_trades_today, daily_realized_pnl

    open_count = count_open_positions(conn)
    if open_count >= config.max_open_positions:
        return GateResult.reject(
            f"max_open_positions: {open_count} >= {config.max_open_positions}"
        )

    trades_today = count_trades_today(conn)
    if trades_today >= config.max_trades_per_day:
        return GateResult.reject(
            f"max_trades_per_day: {trades_today} >= {config.max_trades_per_day}"
        )

    realized_pnl = daily_realized_pnl(conn)
    # If already at loss cap, or would breach with this trade's full risk
    if realized_pnl <= -config.max_daily_loss_usd:
        return GateResult.reject(
            f"daily_loss_cap: realized PnL ${realized_pnl:.2f} "
            f"already at/beyond -${config.max_daily_loss_usd:.2f}"
        )

    if realized_pnl - risk_dollars < -config.max_daily_loss_usd:
        return GateResult.reject(
            f"daily_loss_cap: realized PnL ${realized_pnl:.2f} - "
            f"risk ${risk_dollars:.2f} would breach -${config.max_daily_loss_usd:.2f}"
        )

    return GateResult.ok()
