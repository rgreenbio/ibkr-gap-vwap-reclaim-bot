"""IBKR market scanner for discovering gap-down candidates."""

from __future__ import annotations

import logging

logger = logging.getLogger("gap_vwap_bot.scanner")


def scan_top_losers(
    ib,
    min_price: float = 10.0,
    min_volume: int = 1_000_000,
    max_results: int = 50,
) -> list[str]:
    """Use IBKR scanner to find top percentage losers among US equities.

    Returns a list of ticker symbols.
    """
    from ib_insync import ScannerSubscription

    sub = ScannerSubscription(
        instrument="STK",
        locationCode="STK.US.MAJOR",
        scanCode="TOP_PERC_LOSE",
        abovePrice=min_price,
        aboveVolume=min_volume,
        numberOfRows=max_results,
    )

    results = ib.reqScannerSubscription(sub)
    ib.sleep(2)

    tickers = []
    for item in results:
        symbol = item.contractDetails.contract.symbol
        tickers.append(symbol)

    ib.cancelScannerSubscription(results)

    logger.info(f"Scanner found {len(tickers)} top losers: {tickers[:10]}...")
    return tickers
