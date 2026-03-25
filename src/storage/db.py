"""SQLite database initialisation and connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    prior_close         REAL,
    current_price       REAL,
    gap_pct             REAL,
    avg_daily_volume    REAL,
    premarket_volume    REAL,
    premarket_dollar_volume REAL,
    pass_fail           TEXT,
    rejection_reasons   TEXT,
    detected_at         TEXT,
    session_date        TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id            TEXT PRIMARY KEY,
    ticker              TEXT NOT NULL,
    state               TEXT NOT NULL,
    entry_price         REAL,
    stop_price          REAL,
    target_price        REAL,
    shares              INTEGER,
    risk_dollars        REAL,
    setup_low           REAL,
    fill_price          REAL,
    fill_time           TEXT,
    exit_price          REAL,
    exit_time           TEXT,
    exit_reason         TEXT,
    pnl_dollars         REAL,
    pnl_pct             REAL,
    max_favorable_excursion REAL,
    max_adverse_excursion   REAL,
    ibkr_order_id       INTEGER,
    ibkr_parent_order_id INTEGER,
    features_json       TEXT,
    session_date        TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id            TEXT NOT NULL,
    from_state          TEXT,
    to_state            TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    metadata_json       TEXT,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

CREATE TABLE IF NOT EXISTS daily_summary (
    session_date        TEXT PRIMARY KEY,
    trades_taken        INTEGER,
    wins                INTEGER,
    losses              INTEGER,
    gross_pnl           REAL,
    max_drawdown        REAL,
    candidates_found    INTEGER,
    signals_generated   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_trades_state ON trades(state);
CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_date);
CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidates(session_date);
CREATE INDEX IF NOT EXISTS idx_transitions_trade ON state_transitions(trade_id);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
