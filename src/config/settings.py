"""Configuration loading: .env for IBKR connection, YAML files for strategy/risk/universe."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


# ---------------------------------------------------------------------------
# IBKR connection settings (from .env)
# ---------------------------------------------------------------------------

class IbkrSettings(BaseSettings):
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002
    ibkr_client_id: int = 30
    db_path: str = "data/trades.db"
    log_level: str = "INFO"

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def resolved_db_path(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


# ---------------------------------------------------------------------------
# YAML config models
# ---------------------------------------------------------------------------

class StretchConfig(BaseModel):
    rsi_period: int = 5
    rsi_max: float = 25.0
    min_distance_below_vwap_pct: float = 0.5


class EntryConfig(BaseModel):
    trigger: str = "vwap_reclaim"
    reclaim_bar_timeframe: str = "1m"


class StopConfig(BaseModel):
    type: str = "below_setup_low"
    buffer_pct: float = 0.1


class TargetConfig(BaseModel):
    type: str = "fixed_r_multiple"
    r_multiple: float = 2.0


class StrategyConfig(BaseModel):
    gap_down_min_pct: float = 5.0
    price_min: float = 10.0
    entry_window_start_pt: str = "06:30"
    entry_window_end_pt: str = "08:00"
    flatten_time_pt: str = "12:45"
    stretch: StretchConfig = StretchConfig()
    entry: EntryConfig = EntryConfig()
    stop: StopConfig = StopConfig()
    target: TargetConfig = TargetConfig()


class UniverseConfig(BaseModel):
    min_price: float = 10.0
    min_avg_daily_volume: int = 1_000_000
    min_premarket_volume: int = 100_000
    min_premarket_dollar_volume: int = 2_000_000
    exclude_otc: bool = True


class RiskConfig(BaseModel):
    risk_per_trade_usd: float = 100.0
    max_daily_loss_usd: float = 300.0
    max_open_positions: int = 1
    max_trades_per_day: int = 3
    min_reward_risk: float = 2.0
    max_position_notional_usd: float = 25_000.0
    min_stop_distance_pct: float = 0.1
    max_stop_distance_pct: float = 10.0


class ScheduleConfig(BaseModel):
    timezone: str = "America/Los_Angeles"
    scan_start_pt: str = "06:00"
    active_window_start_pt: str = "06:30"
    active_window_end_pt: str = "08:00"
    flatten_time_pt: str = "12:45"
    scan_interval_seconds: int = 30
    monitor_interval_seconds: int = 5


class ExclusionsConfig(BaseModel):
    excluded_tickers: list[str] = []
    exclude_leveraged_etfs: bool = True
    leveraged_etf_patterns: list[str] = []
    excluded_keywords: list[str] = []


class AppConfig(BaseModel):
    strategy: StrategyConfig = StrategyConfig()
    universe: UniverseConfig = UniverseConfig()
    risk: RiskConfig = RiskConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    exclusions: ExclusionsConfig = ExclusionsConfig()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_yaml_config(config_dir: Path | None = None) -> AppConfig:
    """Load all YAML config files and return a validated AppConfig."""
    d = config_dir or CONFIG_DIR
    return AppConfig(
        strategy=StrategyConfig(**_load_yaml(d / "strategy.yaml")),
        universe=UniverseConfig(**_load_yaml(d / "universe.yaml")),
        risk=RiskConfig(**_load_yaml(d / "risk.yaml")),
        schedule=ScheduleConfig(**_load_yaml(d / "schedule.yaml")),
        exclusions=ExclusionsConfig(**_load_yaml(d / "exclusions.yaml")),
    )


_settings: IbkrSettings | None = None


def get_settings() -> IbkrSettings:
    global _settings
    if _settings is None:
        _settings = IbkrSettings()
    return _settings
