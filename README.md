# IBKR Gap-Down VWAP Reclaim Bot

A rule-driven **paper-trading** bot for one narrow intraday setup:

**Long-only on US equities that gap down ≥5%, become oversold, and reclaim VWAP during the morning session.**

## What It Does

1. **Scans** a watchlist premarket for stocks gapping down ≥5%
2. **Filters** by liquidity, price, and exclusion rules
3. **Monitors** candidates for oversold stretch (RSI ≤ 25 on 1-min bars, price below VWAP)
4. **Triggers** entry when price reclaims VWAP with ≥2:1 reward-to-risk
5. **Places** a bracket order (entry + stop + target) via IBKR paper account
6. **Manages** the position: target hit, stop hit, or force-flatten before close

## What It Does NOT Do

- Trade live capital
- Short stocks
- Trade multiple setup families
- Use machine learning or LLMs in the decision loop
- Make discretionary news judgments
- Hold positions overnight
- Trade after the morning window

## Setup

### Requirements

- Python 3.11+
- IB Gateway or TWS (paper trading account)
- IB Gateway running on port 4002

### Install

```bash
git clone <repo-url>
cd ibkr-gap-vwap-reclaim-bot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your IBKR connection settings
```

Configuration files in `config/`:
- `strategy.yaml` — gap threshold, RSI, VWAP, stop/target parameters
- `universe.yaml` — price and volume filters
- `risk.yaml` — per-trade risk, daily loss cap, position limits
- `schedule.yaml` — session windows (all Pacific time)
- `exclusions.yaml` — blocked tickers and keywords

### Initialize Database

```bash
gap-vwap-bot init
```

## Usage

### One-shot scan
```bash
gap-vwap-bot scan --watchlist "AAPL,TSLA,NVDA,META,AMD"
```

### Full session (scan + monitor + trade + flatten)
```bash
gap-vwap-bot run --watchlist "AAPL,TSLA,NVDA,META,AMD"
```

### Dry run (log signals, no orders)
```bash
gap-vwap-bot run --watchlist "AAPL,TSLA,NVDA" --dry-run
```

### Daily report
```bash
gap-vwap-bot report
gap-vwap-bot report --date 2026-03-20 --csv outputs/trades.csv
```

### Current status
```bash
gap-vwap-bot status
```

## Risk Controls

| Control | Default |
|---------|---------|
| Risk per trade | $100 |
| Max daily loss | $300 |
| Max open positions | 1 |
| Max trades per day | 3 |
| Min reward:risk | 2.0 |
| Entry window | 6:30–8:00 AM PT |
| Flatten deadline | 12:45 PM PT |
| Paper trading only | Port 4002 enforced |

## Artifacts

Per session day in `outputs/`:
- `events/YYYY-MM-DD/{TICKER}.jsonl` — per-ticker event log
- `orders/YYYY-MM-DD/*.json` — order submission logs
- `reports/YYYY-MM-DD/daily_report.md` — markdown summary
- `logs/YYYY-MM-DD.log` — full session log

## IBKR Paper Setup

1. Download and install IB Gateway from Interactive Brokers
2. Create a paper trading account
3. Launch IB Gateway, select "Paper Trading" mode
4. Ensure it's listening on port 4002
5. Ensure market data subscriptions are active (or delayed data will be used)

## Scheduling

Use cron or launchd to start the session daily:

```bash
# cron example: start at 6:00 AM PT on weekdays
0 6 * * 1-5 /path/to/scripts/run_session.sh AAPL,TSLA,NVDA,META
```

## Tests

```bash
pytest tests/ -v
```

## Limitations

- Watchlist is manual (no scanner integration in V1)
- No catastrophic-news auto-detection (manual exclusion only)
- Single position at a time
- No trailing stops or dynamic exits
- No spread-aware entry logic
- No backtest/replay harness
