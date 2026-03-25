"""Domain models for the gap-down VWAP reclaim strategy."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TradeState(str, Enum):
    CANDIDATE_DETECTED = "candidate_detected"
    STRETCH_CONFIRMED = "stretch_confirmed"
    VWAP_RECLAIM_TRIGGERED = "vwap_reclaim_triggered"
    RISK_VALIDATED = "risk_validated"
    PAPER_ORDER_SUBMITTED = "paper_order_submitted"
    PAPER_ORDER_FILLED = "paper_order_filled"
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    TIME_EXIT = "time_exit"
    CLOSED = "closed"


# Valid state transitions
_VALID_TRANSITIONS: dict[TradeState, set[TradeState]] = {
    TradeState.CANDIDATE_DETECTED: {TradeState.STRETCH_CONFIRMED},
    TradeState.STRETCH_CONFIRMED: {TradeState.VWAP_RECLAIM_TRIGGERED},
    TradeState.VWAP_RECLAIM_TRIGGERED: {TradeState.RISK_VALIDATED},
    TradeState.RISK_VALIDATED: {TradeState.PAPER_ORDER_SUBMITTED},
    TradeState.PAPER_ORDER_SUBMITTED: {TradeState.PAPER_ORDER_FILLED, TradeState.CLOSED},
    TradeState.PAPER_ORDER_FILLED: {
        TradeState.TARGET_HIT,
        TradeState.STOP_HIT,
        TradeState.TIME_EXIT,
    },
    TradeState.TARGET_HIT: {TradeState.CLOSED},
    TradeState.STOP_HIT: {TradeState.CLOSED},
    TradeState.TIME_EXIT: {TradeState.CLOSED},
    TradeState.CLOSED: set(),
}


class Candidate(BaseModel):
    """A stock that passed gap-down screening."""
    ticker: str
    prior_close: float
    current_price: float
    gap_pct: float
    avg_daily_volume: float = 0.0
    premarket_volume: float = 0.0
    premarket_dollar_volume: float = 0.0
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_date: str = ""
    pass_fail: str = "pass"
    rejection_reasons: list[str] = Field(default_factory=list)


class StretchSignal(BaseModel):
    """Indicates a stock has become oversold/stretched after gapping down."""
    ticker: str
    rsi_value: float
    vwap: float
    price: float
    vwap_distance_pct: float
    flush_low: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EntrySignal(BaseModel):
    """A fully qualified entry signal with stop, target, and sizing."""
    ticker: str
    entry_price: float
    stop_price: float
    target_price: float
    shares: int
    risk_dollars: float
    reward_risk_ratio: float
    setup_low: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaperTrade(BaseModel):
    """A paper trade through its full lifecycle."""
    trade_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    ticker: str
    state: TradeState = TradeState.CANDIDATE_DETECTED

    # Entry
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    shares: int = 0
    risk_dollars: float = 0.0
    setup_low: float | None = None

    # Fill
    fill_price: float | None = None
    fill_time: datetime | None = None

    # Exit
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None

    # P&L
    pnl_dollars: float | None = None
    pnl_pct: float | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None

    # IBKR
    ibkr_order_id: int | None = None
    ibkr_parent_order_id: int | None = None

    # Metadata
    features: dict[str, Any] = Field(default_factory=dict)
    session_date: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def transition(self, new_state: TradeState) -> None:
        """Transition to a new state, validating the transition is legal."""
        allowed = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: {self.state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

    def compute_pnl(self) -> None:
        """Compute P&L from fill and exit prices."""
        if self.fill_price is None or self.exit_price is None or self.shares == 0:
            return
        self.pnl_dollars = round((self.exit_price - self.fill_price) * self.shares, 2)
        self.pnl_pct = round((self.exit_price - self.fill_price) / self.fill_price * 100, 2)

    @property
    def is_open(self) -> bool:
        return self.state not in (TradeState.CLOSED,)

    @property
    def is_filled(self) -> bool:
        return self.state in (
            TradeState.PAPER_ORDER_FILLED,
            TradeState.TARGET_HIT,
            TradeState.STOP_HIT,
            TradeState.TIME_EXIT,
        )
