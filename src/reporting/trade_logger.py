"""Per-ticker JSONL event logging for audit trail."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _log_dir() -> Path:
    today = datetime.now(PT).strftime("%Y-%m-%d")
    d = PROJECT_ROOT / "outputs" / "events" / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_trade_event(ticker: str, event_type: str, data: dict[str, Any]) -> None:
    """Append a structured event to the ticker's JSONL file."""
    path = _log_dir() / f"{ticker}.jsonl"
    event = {
        "timestamp": datetime.now(PT).isoformat(),
        "ticker": ticker,
        "event": event_type,
        **data,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def log_candidate_detected(ticker: str, gap_pct: float, price: float, **kwargs) -> None:
    log_trade_event(ticker, "candidate_detected", {
        "gap_pct": gap_pct, "price": price, **kwargs,
    })


def log_stretch_confirmed(ticker: str, rsi: float, vwap_dist: float, **kwargs) -> None:
    log_trade_event(ticker, "stretch_confirmed", {
        "rsi": rsi, "vwap_distance_pct": vwap_dist, **kwargs,
    })


def log_entry_triggered(ticker: str, entry: float, stop: float, target: float, shares: int) -> None:
    log_trade_event(ticker, "entry_triggered", {
        "entry_price": entry, "stop_price": stop, "target_price": target, "shares": shares,
    })


def log_fill(ticker: str, fill_price: float, shares: int) -> None:
    log_trade_event(ticker, "filled", {"fill_price": fill_price, "shares": shares})


def log_exit(ticker: str, exit_price: float, reason: str, pnl: float | None) -> None:
    log_trade_event(ticker, "exit", {
        "exit_price": exit_price, "reason": reason, "pnl_dollars": pnl,
    })


def log_rejection(ticker: str, reason: str) -> None:
    log_trade_event(ticker, "rejected", {"reason": reason})
