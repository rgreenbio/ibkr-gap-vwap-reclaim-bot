"""Premarket candidate scanning job."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.fetch import get_avg_daily_volume, get_premarket_data, get_prior_close, get_snapshot
from src.config.settings import AppConfig
from src.indicators.gap import compute_gap_pct, is_gap_down
from src.models.domain import Candidate
from src.reporting.trade_logger import log_candidate_detected, log_rejection
from src.storage.repositories import insert_candidate
from src.strategy.universe_filter import filter_candidate

logger = logging.getLogger("gap_vwap_bot.scan")

PT = ZoneInfo("America/Los_Angeles")


def run_scan(
    ib,
    conn: sqlite3.Connection,
    config: AppConfig,
    watchlist: list[str],
) -> dict:
    """Scan watchlist for gap-down candidates.

    Returns summary dict with counts.
    """
    today = datetime.now(PT).strftime("%Y-%m-%d")
    scanned = 0
    passed = 0
    failed = 0

    for ticker in watchlist:
        scanned += 1
        try:
            snap = get_snapshot(ib, ticker)
            current_price = snap.get("last")
            if current_price is None:
                logger.debug(f"{ticker}: no price data, skipping")
                continue

            prior_close = get_prior_close(ib, ticker)
            if prior_close is None:
                logger.debug(f"{ticker}: no prior close, skipping")
                continue

            gap_pct = compute_gap_pct(current_price, prior_close)

            # Quick gap check before expensive data fetches
            if not is_gap_down(gap_pct, config.strategy.gap_down_min_pct):
                continue

            avg_vol = get_avg_daily_volume(ib, ticker) or 0
            premarket = get_premarket_data(ib, ticker)

            result = filter_candidate(
                ticker=ticker,
                price=current_price,
                avg_daily_volume=avg_vol,
                premarket_volume=premarket["premarket_volume"],
                premarket_dollar_volume=premarket["premarket_dollar_volume"],
                is_otc=False,
                universe=config.universe,
                exclusions=config.exclusions,
            )

            candidate = Candidate(
                ticker=ticker,
                prior_close=prior_close,
                current_price=current_price,
                gap_pct=gap_pct,
                avg_daily_volume=avg_vol,
                premarket_volume=premarket["premarket_volume"],
                premarket_dollar_volume=premarket["premarket_dollar_volume"],
                session_date=today,
                pass_fail="pass" if result.eligible else "fail",
                rejection_reasons=result.rejection_reasons,
            )
            insert_candidate(conn, candidate)

            if result.eligible:
                passed += 1
                log_candidate_detected(ticker, gap_pct, current_price)
                logger.info(
                    f"{ticker}: GAP DOWN {gap_pct:.1f}% — "
                    f"price=${current_price:.2f}, prior_close=${prior_close:.2f}"
                )
            else:
                failed += 1
                log_rejection(ticker, "; ".join(result.rejection_reasons))
                logger.debug(f"{ticker}: rejected — {result.rejection_reasons}")

        except Exception as e:
            logger.warning(f"{ticker}: scan error — {e}")

    logger.info(f"Scan complete: {scanned} scanned, {passed} passed, {failed} failed")
    return {"scanned": scanned, "passed": passed, "failed": failed}
