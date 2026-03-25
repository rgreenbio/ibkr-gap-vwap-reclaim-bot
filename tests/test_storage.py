"""Tests for SQLite storage layer."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models.domain import Candidate, PaperTrade, TradeState
from src.storage.db import init_db
from src.storage.repositories import (
    count_open_positions,
    count_trades_today,
    daily_realized_pnl,
    get_candidates_by_date,
    get_open_trades,
    get_trades_by_date,
    get_transitions,
    insert_candidate,
    insert_trade,
    update_trade_state,
    upsert_daily_summary,
)


class TestDatabase:
    def test_init_creates_tables(self, db_conn):
        tables = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "candidates" in table_names
        assert "trades" in table_names
        assert "state_transitions" in table_names
        assert "daily_summary" in table_names

    def test_wal_mode(self, db_conn):
        row = db_conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


class TestCandidateRepo:
    def test_insert_and_retrieve(self, db_conn):
        c = Candidate(
            ticker="AAPL",
            prior_close=150.0,
            current_price=140.0,
            gap_pct=-6.67,
            session_date="2026-03-20",
        )
        insert_candidate(db_conn, c)

        results = get_candidates_by_date(db_conn, "2026-03-20")
        assert len(results) == 1
        assert results[0].ticker == "AAPL"
        assert results[0].gap_pct == -6.67


class TestTradeRepo:
    def test_insert_and_retrieve(self, db_conn):
        t = PaperTrade(
            trade_id="test001",
            ticker="TSLA",
            state=TradeState.PAPER_ORDER_FILLED,
            entry_price=200.0,
            stop_price=195.0,
            target_price=210.0,
            shares=20,
            risk_dollars=100.0,
            session_date="2026-03-20",
        )
        insert_trade(db_conn, t)

        trades = get_open_trades(db_conn)
        assert len(trades) == 1
        assert trades[0].ticker == "TSLA"
        assert trades[0].state == TradeState.PAPER_ORDER_FILLED

    def test_state_transition_logged(self, db_conn):
        t = PaperTrade(
            trade_id="test002",
            ticker="MSFT",
            state=TradeState.PAPER_ORDER_SUBMITTED,
            session_date="2026-03-20",
        )
        insert_trade(db_conn, t)

        update_trade_state(db_conn, "test002", TradeState.PAPER_ORDER_FILLED)

        transitions = get_transitions(db_conn, "test002")
        assert len(transitions) == 2  # initial insert + update
        assert transitions[0]["to_state"] == TradeState.PAPER_ORDER_SUBMITTED.value
        assert transitions[1]["to_state"] == TradeState.PAPER_ORDER_FILLED.value

    def test_count_open_positions(self, db_conn):
        assert count_open_positions(db_conn) == 0

        t = PaperTrade(
            trade_id="test003",
            ticker="GOOG",
            state=TradeState.PAPER_ORDER_FILLED,
            session_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        insert_trade(db_conn, t)
        assert count_open_positions(db_conn) == 1

    def test_count_trades_today(self, db_conn):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert count_trades_today(db_conn) == 0

        t = PaperTrade(
            trade_id="test004",
            ticker="META",
            state=TradeState.CLOSED,
            session_date=today,
        )
        insert_trade(db_conn, t)
        assert count_trades_today(db_conn) == 1

    def test_daily_realized_pnl(self, db_conn):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert daily_realized_pnl(db_conn) == 0.0

        t = PaperTrade(
            trade_id="test005",
            ticker="AMZN",
            state=TradeState.CLOSED,
            pnl_dollars=-75.0,
            session_date=today,
        )
        insert_trade(db_conn, t)
        update_trade_state(db_conn, "test005", TradeState.CLOSED, pnl_dollars=-75.0)
        assert daily_realized_pnl(db_conn) == -75.0


class TestDailySummary:
    def test_upsert(self, db_conn):
        stats = {
            "trades_taken": 2,
            "wins": 1,
            "losses": 1,
            "gross_pnl": 50.0,
            "max_drawdown": -100.0,
            "candidates_found": 5,
            "signals_generated": 3,
        }
        upsert_daily_summary(db_conn, "2026-03-20", stats)

        row = db_conn.execute(
            "SELECT * FROM daily_summary WHERE session_date='2026-03-20'"
        ).fetchone()
        assert row["trades_taken"] == 2
        assert row["gross_pnl"] == 50.0

        # Update
        stats["wins"] = 2
        upsert_daily_summary(db_conn, "2026-03-20", stats)
        row = db_conn.execute(
            "SELECT * FROM daily_summary WHERE session_date='2026-03-20'"
        ).fetchone()
        assert row["wins"] == 2
