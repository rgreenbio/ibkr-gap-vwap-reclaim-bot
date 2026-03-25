"""Tests for risk gate logic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config.settings import RiskConfig
from src.models.domain import PaperTrade, TradeState
from src.storage.repositories import insert_trade, update_trade_state
from src.strategy.risk_gate import apply_risk_gate


@pytest.fixture
def risk_config() -> RiskConfig:
    return RiskConfig(
        risk_per_trade_usd=100.0,
        max_daily_loss_usd=300.0,
        max_open_positions=1,
        max_trades_per_day=3,
    )


def _make_trade(trade_id: str, state: TradeState, **kwargs) -> PaperTrade:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return PaperTrade(
        trade_id=trade_id,
        ticker="TEST",
        state=state,
        entry_price=50.0,
        stop_price=48.0,
        target_price=54.0,
        shares=50,
        risk_dollars=100.0,
        session_date=today,
        **kwargs,
    )


class TestRiskGate:
    def test_approved_when_clean(self, db_conn, risk_config):
        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is True

    def test_rejects_max_open_positions(self, db_conn, risk_config):
        trade = _make_trade("t1", TradeState.PAPER_ORDER_FILLED)
        insert_trade(db_conn, trade)

        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is False
        assert "max_open_positions" in result.reason

    def test_rejects_max_trades_per_day(self, db_conn, risk_config):
        for i in range(3):
            trade = _make_trade(f"t{i}", TradeState.CLOSED, pnl_dollars=10.0)
            insert_trade(db_conn, trade)
            update_trade_state(db_conn, f"t{i}", TradeState.CLOSED, pnl_dollars=10.0)

        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is False
        assert "max_trades_per_day" in result.reason

    def test_rejects_daily_loss_cap_already_breached(self, db_conn, risk_config):
        for i in range(3):
            trade = _make_trade(f"t{i}", TradeState.CLOSED, pnl_dollars=-100.0)
            insert_trade(db_conn, trade)
            update_trade_state(db_conn, f"t{i}", TradeState.CLOSED, pnl_dollars=-100.0)

        # Update config to allow more trades
        risk_config.max_trades_per_day = 10
        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is False
        assert "daily_loss_cap" in result.reason

    def test_rejects_daily_loss_cap_would_breach(self, db_conn, risk_config):
        trade = _make_trade("t1", TradeState.CLOSED, pnl_dollars=-250.0)
        insert_trade(db_conn, trade)
        update_trade_state(db_conn, "t1", TradeState.CLOSED, pnl_dollars=-250.0)

        risk_config.max_trades_per_day = 10
        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is False
        assert "daily_loss_cap" in result.reason

    def test_approved_with_small_loss(self, db_conn, risk_config):
        trade = _make_trade("t1", TradeState.CLOSED, pnl_dollars=-50.0)
        insert_trade(db_conn, trade)
        update_trade_state(db_conn, "t1", TradeState.CLOSED, pnl_dollars=-50.0)

        risk_config.max_trades_per_day = 10
        result = apply_risk_gate(100.0, db_conn, risk_config)
        assert result.approved is True
