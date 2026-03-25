"""CLI entry point using Typer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="gap-vwap-bot", help="IBKR Gap-Down VWAP Reclaim Paper Trading Bot")
console = Console()
PT = ZoneInfo("America/Los_Angeles")


@app.command()
def init():
    """Initialize the database."""
    from src.config.settings import get_settings
    from src.storage.db import init_db

    settings = get_settings()
    init_db(settings.resolved_db_path)
    console.print(f"Database initialized at {settings.resolved_db_path}")


@app.command()
def scan(
    watchlist: str = typer.Option(
        "",
        help="Comma-separated ticker list (e.g. 'AAPL,TSLA,NVDA')",
    ),
):
    """Run a one-shot premarket candidate scan."""
    from src.clients.tws_client import TWSClient
    from src.config.settings import get_settings, load_yaml_config
    from src.jobs.scan_candidates import run_scan
    from src.storage.db import init_db
    from src.utils.logging import setup_logging

    settings = get_settings()
    config = load_yaml_config()
    setup_logging(settings.log_level)

    tickers = [t.strip().upper() for t in watchlist.split(",") if t.strip()]
    if not tickers:
        console.print("[red]No tickers provided. Use --watchlist 'AAPL,TSLA,...'[/red]")
        raise typer.Exit(1)

    conn = init_db(settings.resolved_db_path)

    with TWSClient() as client:
        result = run_scan(client.ib, conn, config, tickers)

    conn.close()

    console.print(f"\nScan: {result['scanned']} scanned, "
                  f"[green]{result['passed']} passed[/green], "
                  f"[red]{result['failed']} failed[/red]")


@app.command()
def run(
    watchlist: str = typer.Option(
        "",
        help="Comma-separated ticker list",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log signals without placing orders"),
):
    """Run the full intraday session (scan + monitor + trade + flatten)."""
    from src.config.settings import load_yaml_config
    from src.jobs.run_session import run_session

    config = load_yaml_config()
    tickers = [t.strip().upper() for t in watchlist.split(",") if t.strip()] or None

    console.print(f"Starting session {'(DRY RUN)' if dry_run else ''}")
    result = run_session(config=config, watchlist=tickers, dry_run=dry_run)

    table = Table(title="Session Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for k, v in result.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command()
def report(
    date: str = typer.Option("", help="Session date (YYYY-MM-DD). Defaults to today."),
    csv_path: str = typer.Option("", "--csv", help="Export trades to CSV at this path."),
):
    """Generate a daily report."""
    from src.config.settings import get_settings
    from src.reporting.daily_report import export_trades_csv, generate_daily_report
    from src.storage.db import init_db

    settings = get_settings()
    conn = init_db(settings.resolved_db_path)

    session_date = date or datetime.now(PT).strftime("%Y-%m-%d")
    md = generate_daily_report(conn, session_date)
    console.print(md)

    if csv_path:
        export_trades_csv(conn, session_date, Path(csv_path))
        console.print(f"\nCSV exported to {csv_path}")

    # Save markdown report
    report_dir = Path("outputs/reports") / session_date
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "daily_report.md"
    report_path.write_text(md, encoding="utf-8")
    console.print(f"Report saved to {report_path}")

    conn.close()


@app.command()
def status():
    """Show current open positions and daily stats."""
    from src.config.settings import get_settings
    from src.storage.db import init_db
    from src.storage.repositories import count_open_positions, count_trades_today, daily_realized_pnl, get_open_trades

    settings = get_settings()
    conn = init_db(settings.resolved_db_path)

    open_count = count_open_positions(conn)
    trades_today = count_trades_today(conn)
    pnl = daily_realized_pnl(conn)

    table = Table(title="Current Status")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Open positions", str(open_count))
    table.add_row("Trades today", str(trades_today))
    table.add_row("Realized P&L", f"${pnl:.2f}")
    console.print(table)

    open_trades = get_open_trades(conn)
    if open_trades:
        pos_table = Table(title="Open Trades")
        pos_table.add_column("ID")
        pos_table.add_column("Ticker")
        pos_table.add_column("State")
        pos_table.add_column("Entry")
        pos_table.add_column("Stop")
        pos_table.add_column("Target")
        pos_table.add_column("Shares")
        for t in open_trades:
            pos_table.add_row(
                t.trade_id[:8],
                t.ticker,
                t.state.value,
                f"${t.entry_price:.2f}" if t.entry_price else "—",
                f"${t.stop_price:.2f}" if t.stop_price else "—",
                f"${t.target_price:.2f}" if t.target_price else "—",
                str(t.shares),
            )
        console.print(pos_table)

    conn.close()


if __name__ == "__main__":
    app()
