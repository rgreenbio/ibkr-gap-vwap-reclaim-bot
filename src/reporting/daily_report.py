"""Daily report generation in Markdown and CSV formats."""

from __future__ import annotations

import csv
import sqlite3
from io import StringIO
from pathlib import Path

from src.storage.repositories import get_candidates_by_date, get_trades_by_date


def generate_daily_report(conn: sqlite3.Connection, session_date: str) -> str:
    """Generate a Markdown daily summary report."""
    trades = get_trades_by_date(conn, session_date)
    candidates = get_candidates_by_date(conn, session_date)

    closed = [t for t in trades if t.pnl_dollars is not None]
    wins = [t for t in closed if t.pnl_dollars and t.pnl_dollars > 0]
    losses = [t for t in closed if t.pnl_dollars is not None and t.pnl_dollars <= 0]
    gross_pnl = sum(t.pnl_dollars for t in closed if t.pnl_dollars)

    lines = [
        f"# Daily Report — {session_date}",
        "",
        "## Session Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Candidates scanned | {len(candidates)} |",
        f"| Candidates passed | {len([c for c in candidates if c.pass_fail == 'pass'])} |",
        f"| Trades taken | {len(trades)} |",
        f"| Wins | {len(wins)} |",
        f"| Losses | {len(losses)} |",
        f"| Gross P&L | ${gross_pnl:.2f} |",
        "",
    ]

    if trades:
        lines.append("## Trade Details")
        lines.append("")
        for t in trades:
            lines.append(f"### {t.ticker} ({t.trade_id})")
            lines.append("")
            lines.append(f"- **State:** {t.state.value}")
            lines.append(f"- **Entry:** ${t.entry_price}" if t.entry_price else "- **Entry:** —")
            lines.append(f"- **Fill:** ${t.fill_price}" if t.fill_price else "- **Fill:** —")
            lines.append(f"- **Stop:** ${t.stop_price}" if t.stop_price else "- **Stop:** —")
            lines.append(f"- **Target:** ${t.target_price}" if t.target_price else "- **Target:** —")
            lines.append(f"- **Shares:** {t.shares}")
            lines.append(f"- **Risk:** ${t.risk_dollars:.2f}")
            if t.exit_price:
                lines.append(f"- **Exit:** ${t.exit_price} ({t.exit_reason})")
            if t.pnl_dollars is not None:
                lines.append(f"- **P&L:** ${t.pnl_dollars:.2f} ({t.pnl_pct:.1f}%)")
            if t.max_favorable_excursion is not None:
                lines.append(f"- **MFE:** ${t.max_favorable_excursion:.2f}")
            if t.max_adverse_excursion is not None:
                lines.append(f"- **MAE:** ${t.max_adverse_excursion:.2f}")
            lines.append("")

    if candidates:
        lines.append("## Candidate Log")
        lines.append("")
        lines.append("| Ticker | Gap% | Price | Prior Close | Pass/Fail | Reasons |")
        lines.append("|--------|------|-------|-------------|-----------|---------|")
        for c in candidates:
            reasons = "; ".join(c.rejection_reasons) if c.rejection_reasons else "—"
            lines.append(
                f"| {c.ticker} | {c.gap_pct:.1f}% | ${c.current_price:.2f} "
                f"| ${c.prior_close:.2f} | {c.pass_fail} | {reasons} |"
            )
        lines.append("")

    return "\n".join(lines)


def export_trades_csv(conn: sqlite3.Connection, session_date: str, path: Path) -> None:
    """Export trades for a session date to CSV."""
    trades = get_trades_by_date(conn, session_date)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "trade_id", "ticker", "state", "entry_price", "fill_price",
            "stop_price", "target_price", "shares", "risk_dollars",
            "exit_price", "exit_reason", "pnl_dollars", "pnl_pct",
            "mfe", "mae", "session_date",
        ])
        for t in trades:
            writer.writerow([
                t.trade_id, t.ticker, t.state.value,
                t.entry_price, t.fill_price,
                t.stop_price, t.target_price,
                t.shares, t.risk_dollars,
                t.exit_price, t.exit_reason,
                t.pnl_dollars, t.pnl_pct,
                t.max_favorable_excursion, t.max_adverse_excursion,
                t.session_date,
            ])
