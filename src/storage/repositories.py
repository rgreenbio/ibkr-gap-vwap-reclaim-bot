"""Repository helpers wrapping raw SQLite access."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.models.domain import Candidate, PaperTrade, TradeState


# ---------------------------------------------------------------------------
# Candidate repository
# ---------------------------------------------------------------------------

def insert_candidate(conn: sqlite3.Connection, c: Candidate) -> None:
    conn.execute(
        """INSERT INTO candidates
           (ticker, prior_close, current_price, gap_pct, avg_daily_volume,
            premarket_volume, premarket_dollar_volume, pass_fail,
            rejection_reasons, detected_at, session_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            c.ticker, c.prior_close, c.current_price, c.gap_pct,
            c.avg_daily_volume, c.premarket_volume, c.premarket_dollar_volume,
            c.pass_fail, json.dumps(c.rejection_reasons),
            _ts(c.detected_at), c.session_date,
        ),
    )
    conn.commit()


def get_candidates_by_date(conn: sqlite3.Connection, session_date: str) -> list[Candidate]:
    rows = conn.execute(
        "SELECT * FROM candidates WHERE session_date=? ORDER BY gap_pct ASC",
        (session_date,),
    ).fetchall()
    return [_row_to_candidate(r) for r in rows]


# ---------------------------------------------------------------------------
# Trade repository
# ---------------------------------------------------------------------------

def insert_trade(conn: sqlite3.Connection, t: PaperTrade) -> None:
    conn.execute(
        """INSERT INTO trades
           (trade_id, ticker, state, entry_price, stop_price, target_price,
            shares, risk_dollars, setup_low, fill_price, fill_time,
            exit_price, exit_time, exit_reason, pnl_dollars, pnl_pct,
            max_favorable_excursion, max_adverse_excursion,
            ibkr_order_id, ibkr_parent_order_id,
            features_json, session_date, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            t.trade_id, t.ticker, t.state.value,
            t.entry_price, t.stop_price, t.target_price,
            t.shares, t.risk_dollars, t.setup_low,
            t.fill_price, _ts(t.fill_time),
            t.exit_price, _ts(t.exit_time), t.exit_reason,
            t.pnl_dollars, t.pnl_pct,
            t.max_favorable_excursion, t.max_adverse_excursion,
            t.ibkr_order_id, t.ibkr_parent_order_id,
            json.dumps(t.features), t.session_date,
            _ts(t.created_at), _ts(t.updated_at),
        ),
    )
    conn.commit()

    _insert_transition(conn, t.trade_id, None, t.state.value)


def update_trade_state(
    conn: sqlite3.Connection,
    trade_id: str,
    new_state: TradeState,
    **kwargs: object,
) -> None:
    """Update trade state and any additional fields. Also logs the transition."""
    row = conn.execute("SELECT state FROM trades WHERE trade_id=?", (trade_id,)).fetchone()
    old_state = row["state"] if row else None

    sets = ["state=?", "updated_at=?"]
    vals: list[object] = [new_state.value, _ts(datetime.now(timezone.utc))]

    for col, val in kwargs.items():
        if col == "features":
            sets.append("features_json=?")
            vals.append(json.dumps(val))
        elif col in ("fill_time", "exit_time"):
            sets.append(f"{col}=?")
            vals.append(_ts(val) if val else None)
        else:
            sets.append(f"{col}=?")
            vals.append(val)

    vals.append(trade_id)
    conn.execute(
        f"UPDATE trades SET {', '.join(sets)} WHERE trade_id=?",
        tuple(vals),
    )
    conn.commit()

    _insert_transition(conn, trade_id, old_state, new_state.value)


def get_open_trades(conn: sqlite3.Connection) -> list[PaperTrade]:
    """Get all trades that are not in CLOSED state."""
    rows = conn.execute(
        "SELECT * FROM trades WHERE state != ?",
        (TradeState.CLOSED.value,),
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def get_filled_trades(conn: sqlite3.Connection) -> list[PaperTrade]:
    """Get trades that have been filled and need monitoring."""
    rows = conn.execute(
        "SELECT * FROM trades WHERE state = ?",
        (TradeState.PAPER_ORDER_FILLED.value,),
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def count_open_positions(conn: sqlite3.Connection) -> int:
    """Count trades that are actively holding a position (filled but not exited)."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM trades WHERE state = ?",
        (TradeState.PAPER_ORDER_FILLED.value,),
    ).fetchone()
    return row["cnt"]


def count_trades_today(conn: sqlite3.Connection) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM trades WHERE session_date = ?",
        (today,),
    ).fetchone()
    return row["cnt"]


def daily_realized_pnl(conn: sqlite3.Connection) -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(pnl_dollars), 0.0) as total FROM trades "
        "WHERE session_date = ? AND state = ?",
        (today, TradeState.CLOSED.value),
    ).fetchone()
    return row["total"]


def get_trades_by_date(conn: sqlite3.Connection, session_date: str) -> list[PaperTrade]:
    rows = conn.execute(
        "SELECT * FROM trades WHERE session_date = ? ORDER BY created_at",
        (session_date,),
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


# ---------------------------------------------------------------------------
# State transition log
# ---------------------------------------------------------------------------

def _insert_transition(
    conn: sqlite3.Connection,
    trade_id: str,
    from_state: str | None,
    to_state: str,
    metadata: dict | None = None,
) -> None:
    conn.execute(
        """INSERT INTO state_transitions (trade_id, from_state, to_state, timestamp, metadata_json)
           VALUES (?,?,?,?,?)""",
        (
            trade_id, from_state, to_state,
            _ts(datetime.now(timezone.utc)),
            json.dumps(metadata) if metadata else None,
        ),
    )
    conn.commit()


def get_transitions(conn: sqlite3.Connection, trade_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM state_transitions WHERE trade_id=? ORDER BY timestamp",
        (trade_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

def upsert_daily_summary(conn: sqlite3.Connection, session_date: str, stats: dict) -> None:
    conn.execute(
        """INSERT INTO daily_summary
           (session_date, trades_taken, wins, losses, gross_pnl, max_drawdown,
            candidates_found, signals_generated)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(session_date) DO UPDATE SET
             trades_taken=excluded.trades_taken, wins=excluded.wins,
             losses=excluded.losses, gross_pnl=excluded.gross_pnl,
             max_drawdown=excluded.max_drawdown,
             candidates_found=excluded.candidates_found,
             signals_generated=excluded.signals_generated""",
        (
            session_date,
            stats.get("trades_taken", 0),
            stats.get("wins", 0),
            stats.get("losses", 0),
            stats.get("gross_pnl", 0.0),
            stats.get("max_drawdown", 0.0),
            stats.get("candidates_found", 0),
            stats.get("signals_generated", 0),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------

def _row_to_candidate(row: sqlite3.Row) -> Candidate:
    return Candidate(
        ticker=row["ticker"],
        prior_close=row["prior_close"],
        current_price=row["current_price"],
        gap_pct=row["gap_pct"],
        avg_daily_volume=row["avg_daily_volume"] or 0,
        premarket_volume=row["premarket_volume"] or 0,
        premarket_dollar_volume=row["premarket_dollar_volume"] or 0,
        pass_fail=row["pass_fail"] or "pass",
        rejection_reasons=json.loads(row["rejection_reasons"]) if row["rejection_reasons"] else [],
        detected_at=_parse_ts(row["detected_at"]) or datetime.now(timezone.utc),
        session_date=row["session_date"] or "",
    )


def _row_to_trade(row: sqlite3.Row) -> PaperTrade:
    return PaperTrade(
        trade_id=row["trade_id"],
        ticker=row["ticker"],
        state=TradeState(row["state"]),
        entry_price=row["entry_price"],
        stop_price=row["stop_price"],
        target_price=row["target_price"],
        shares=row["shares"] or 0,
        risk_dollars=row["risk_dollars"] or 0.0,
        setup_low=row["setup_low"],
        fill_price=row["fill_price"],
        fill_time=_parse_ts(row["fill_time"]),
        exit_price=row["exit_price"],
        exit_time=_parse_ts(row["exit_time"]),
        exit_reason=row["exit_reason"],
        pnl_dollars=row["pnl_dollars"],
        pnl_pct=row["pnl_pct"],
        max_favorable_excursion=row["max_favorable_excursion"],
        max_adverse_excursion=row["max_adverse_excursion"],
        ibkr_order_id=row["ibkr_order_id"],
        ibkr_parent_order_id=row["ibkr_parent_order_id"],
        features=json.loads(row["features_json"]) if row["features_json"] else {},
        session_date=row["session_date"] or "",
        created_at=_parse_ts(row["created_at"]) or datetime.now(timezone.utc),
        updated_at=_parse_ts(row["updated_at"]) or datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
