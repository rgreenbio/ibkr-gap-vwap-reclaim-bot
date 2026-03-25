"""Main session orchestrator — runs the full intraday loop."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.fetch import get_historical_bars_1min
from src.clients.tws_client import TWSClient
from src.config.settings import AppConfig, get_settings, load_yaml_config
from src.execution.trade_manager import execute_entry, flatten_all, manage_open_positions
from src.models.domain import TradeState
from src.reporting.trade_logger import log_entry_triggered, log_rejection, log_stretch_confirmed
from src.storage.db import init_db
from src.storage.repositories import (
    count_open_positions,
    get_candidates_by_date,
    get_open_trades,
    upsert_daily_summary,
)
from src.strategy.risk_gate import apply_risk_gate
from src.strategy.setup_detector import compute_entry_signal, detect_stretch, detect_vwap_reclaim
from src.utils.logging import setup_logging
from src.utils.time_utils import (
    is_in_active_window,
    is_in_scan_window,
    is_past_entry_cutoff,
    is_past_flatten_deadline,
    now_pt,
    today_str,
)

logger = logging.getLogger("gap_vwap_bot.session")

PT = ZoneInfo("America/Los_Angeles")


def run_session(
    config: AppConfig | None = None,
    watchlist: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the full intraday session.

    1. Connect to IBKR
    2. Scan for gap-down candidates (premarket)
    3. Monitor for stretch + VWAP reclaim (active window)
    4. Execute entries with risk gate
    5. Monitor open positions
    6. Flatten all before close
    """
    settings = get_settings()
    config = config or load_yaml_config()
    setup_logging(settings.log_level)

    conn = init_db(settings.resolved_db_path)
    today = today_str()

    session_stats = {
        "candidates_found": 0,
        "signals_generated": 0,
        "trades_taken": 0,
        "wins": 0,
        "losses": 0,
        "gross_pnl": 0.0,
        "max_drawdown": 0.0,
    }

    if dry_run:
        logger.info("DRY RUN mode — no orders will be placed")

    with TWSClient() as client:
        ib = client.ib
        logger.info(f"Session started: {today}")

        # Phase 1: Premarket scan
        if not watchlist:
            from src.clients.scanner import scan_top_losers
            logger.info("No watchlist provided — using IBKR scanner for top losers")
            watchlist = scan_top_losers(
                ib,
                min_price=config.universe.min_price,
                min_volume=config.universe.min_avg_daily_volume,
            )

        if watchlist:
            from src.jobs.scan_candidates import run_scan
            scan_result = run_scan(ib, conn, config, watchlist)
            session_stats["candidates_found"] = scan_result["passed"]

        # Phase 2: Active monitoring loop
        # Track which tickers have confirmed stretch
        stretch_tickers: dict[str, dict] = {}

        cycle = 0
        while not is_past_flatten_deadline(config.schedule):
            cycle += 1
            try:
                candidates = get_candidates_by_date(conn, today)
                # Deduplicate by ticker — keep the most recent (last) entry
                seen: dict[str, object] = {}
                for c in candidates:
                    if c.pass_fail == "pass":
                        seen[c.ticker] = c
                passed = list(seen.values())

                if is_in_active_window(config.schedule):
                    logger.info(
                        f"Monitor cycle {cycle}: {len(passed)} candidates, "
                        f"{len(stretch_tickers)} stretched"
                    )
                    for candidate in passed:
                        ticker = candidate.ticker

                        # Skip if already traded or in a stretch-tracking state
                        if ticker in stretch_tickers and stretch_tickers[ticker].get("traded"):
                            continue

                        bars = get_historical_bars_1min(ib, ticker)
                        if bars is None or bars.empty:
                            logger.debug(f"{ticker}: no 1-min bars available")
                            continue

                        # Check for stretch
                        if ticker not in stretch_tickers:
                            stretch = detect_stretch(bars, config.strategy)
                            if stretch:
                                stretch_tickers[ticker] = {
                                    "signal": stretch,
                                    "traded": False,
                                }
                                log_stretch_confirmed(
                                    ticker, stretch.rsi_value, stretch.vwap_distance_pct,
                                )
                                logger.info(
                                    f"{ticker}: STRETCH confirmed — "
                                    f"RSI={stretch.rsi_value}, "
                                    f"VWAP dist={stretch.vwap_distance_pct:.2f}%"
                                )
                            else:
                                from src.indicators.rsi import compute_rsi
                                from src.indicators.vwap import compute_vwap, vwap_distance_pct
                                rsi_val = compute_rsi(bars["close"], config.strategy.stretch.rsi_period)
                                vwap_s = compute_vwap(bars)
                                cur_price = bars["close"].iloc[-1]
                                cur_vwap = vwap_s.iloc[-1]
                                dist = vwap_distance_pct(cur_price, cur_vwap)
                                logger.debug(
                                    f"{ticker}: no stretch — RSI={rsi_val}, "
                                    f"VWAP dist={dist:.2f}%"
                                )

                        # Check for VWAP reclaim on stretched tickers
                        if ticker in stretch_tickers and not stretch_tickers[ticker]["traded"]:
                            if not is_past_entry_cutoff(config.schedule) and detect_vwap_reclaim(bars):
                                stretch_signal = stretch_tickers[ticker]["signal"]
                                entry_price = bars["close"].iloc[-1]

                                entry_signal = compute_entry_signal(
                                    ticker=ticker,
                                    entry_price=entry_price,
                                    flush_low=stretch_signal.flush_low,
                                    strategy=config.strategy,
                                    risk=config.risk,
                                )

                                if entry_signal is None:
                                    log_rejection(ticker, "entry_signal_invalid")
                                    continue

                                # Risk gate
                                gate = apply_risk_gate(
                                    entry_signal.risk_dollars, conn, config.risk,
                                )
                                if not gate.approved:
                                    log_rejection(ticker, gate.reason)
                                    logger.info(f"{ticker}: risk gate REJECTED — {gate.reason}")
                                    continue

                                session_stats["signals_generated"] += 1
                                log_entry_triggered(
                                    ticker, entry_signal.entry_price,
                                    entry_signal.stop_price, entry_signal.target_price,
                                    entry_signal.shares,
                                )

                                if not dry_run:
                                    execute_entry(ib, entry_signal, conn, config)
                                    session_stats["trades_taken"] += 1
                                    stretch_tickers[ticker]["traded"] = True

                                logger.info(
                                    f"{ticker}: VWAP RECLAIM — entry=${entry_signal.entry_price:.2f}"
                                )

                # Monitor open positions (even outside active window)
                if not dry_run:
                    manage_open_positions(ib, conn, config)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)

            time.sleep(config.schedule.monitor_interval_seconds)

        # Phase 3: End of day flatten
        if not dry_run:
            flatten_all(ib, conn, config)

        # Compute final stats
        from src.storage.repositories import get_trades_by_date
        all_trades = get_trades_by_date(conn, today)
        closed = [t for t in all_trades if t.state == TradeState.CLOSED and t.pnl_dollars is not None]
        session_stats["trades_taken"] = len(all_trades)
        session_stats["wins"] = len([t for t in closed if t.pnl_dollars and t.pnl_dollars > 0])
        session_stats["losses"] = len([t for t in closed if t.pnl_dollars is not None and t.pnl_dollars <= 0])
        session_stats["gross_pnl"] = sum(t.pnl_dollars for t in closed if t.pnl_dollars)

        upsert_daily_summary(conn, today, session_stats)
        logger.info(f"Session ended: {session_stats}")

    conn.close()
    return session_stats
