"""Logging setup: console + daily file handler."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root gap_vwap_bot logger with console and file handlers."""
    logger = logging.getLogger("gap_vwap_bot")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Daily file handler
    today = datetime.now(PT).strftime("%Y-%m-%d")
    log_dir = PROJECT_ROOT / "outputs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / f"{today}.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "gap_vwap_bot") -> logging.Logger:
    return logging.getLogger(name)
