"""Time utilities for Pacific timezone session logic."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.config.settings import ScheduleConfig

PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")


def now_pt() -> datetime:
    return datetime.now(PT)


def now_et() -> datetime:
    return datetime.now(ET)


def today_str() -> str:
    return now_pt().strftime("%Y-%m-%d")


def _parse_time(time_str: str) -> time:
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def is_in_scan_window(config: ScheduleConfig) -> bool:
    """True if current time is in the premarket scan window."""
    now = now_pt().time()
    start = _parse_time(config.scan_start_pt)
    end = _parse_time(config.active_window_start_pt)
    return start <= now < end


def is_in_active_window(config: ScheduleConfig) -> bool:
    """True if current time is in the active entry window (6:30-8:00 AM PT)."""
    now = now_pt().time()
    start = _parse_time(config.active_window_start_pt)
    end = _parse_time(config.active_window_end_pt)
    return start <= now < end


def is_past_entry_cutoff(config: ScheduleConfig) -> bool:
    """True if current time is past the entry cutoff."""
    now = now_pt().time()
    end = _parse_time(config.active_window_end_pt)
    return now >= end


def is_past_flatten_deadline(config: ScheduleConfig) -> bool:
    """True if current time is at or past the flatten deadline."""
    now = now_pt().time()
    deadline = _parse_time(config.flatten_time_pt)
    return now >= deadline
