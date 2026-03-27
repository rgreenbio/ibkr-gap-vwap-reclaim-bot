# Claude Cheat Sheet — IBKR Gap-Down VWAP Reclaim Bot

Hand this to a new Claude session for full context.

## Repo
`ibkr-gap-vwap-reclaim-bot` — Rule-driven paper trading bot for gap-down VWAP reclaim setups on US equities via IBKR / IB Gateway.

## What It Does
Scans for US equities gapping down ≥5%, waits for oversold stretch (RSI ≤ 25 + below VWAP), enters on VWAP reclaim with bracket orders (stop + 2R target), flattens before close. Paper trading only.

## How to Run
```bash
cd /path/to/ibkr-gap-vwap-reclaim-bot
source .venv/bin/activate
python -m src.cli run --dry-run          # scanner + signal logging, no orders
python -m src.cli scan --watchlist "AAPL,TSLA"  # one-shot scan
python -m src.cli report                 # daily report
python -m src.cli status                 # current state
```

Without `--watchlist`, the bot uses IBKR's built-in scanner (`TOP_PERC_LOSE`) to auto-discover gap-downs.

## IB Gateway Requirements
- **Port:** 4002 (paper trading)
- **Client ID:** 30
- IB Gateway must be running before the bot starts
- "Read-Only API" setting in IB Gateway blocks order placement but doesn't affect scanning/data

## Known Issues & Lessons Learned

### macOS launchd sandbox blocks venv Python
**Problem:** `PermissionError: Operation not permitted: '.venv/pyvenv.cfg'` when launched via launchd plist.
**Root cause:** macOS sandbox prevents launchd-spawned processes from reading venv files.
**Workaround options:**
1. Grant Full Disk Access to `/usr/bin/python3` in System Preferences → Privacy
2. Use `nohup` from a terminal instead of launchd
3. Use system Python with packages installed globally

### `marketPrice` is a method, not an attribute
**Problem:** `get_snapshot()` returned the method object `ticker.marketPrice` instead of calling it.
**Fix:** `mp() if callable(mp) else mp` in `src/clients/fetch.py:51`

### Delayed data after hours
IB Gateway returns delayed data (type 3) outside market hours. Prices may show as prior close. The bot handles this with `reqMarketDataType(3)`.

### Leveraged/inverse ETFs flood the scanner
**Problem:** `TOP_PERC_LOSE` scanner returns mostly leveraged ETFs (TQQQ, SOXS, UVXY) which aren't real gap-down equity setups.
**Fix:** `config/exclusions.yaml` has a `leveraged_etf_patterns` list. Filter applied in `universe_filter.py`.

### Duplicate candidates in monitor loop
**Problem:** Multiple scan runs per day accumulate duplicate candidates in the DB. Monitor loop processes each one.
**Fix:** Deduplicate by ticker in `run_session.py` before monitoring.

### Session time handling
All user-facing times are Pacific (America/Los_Angeles). Stored as UTC. Entry window: 6:30-8:00 AM PT. Flatten: 12:45 PM PT. Configurable in `config/schedule.yaml`.

### The strategy is strict by design
On the first live data test (2026-03-24), 5 real equity gap-downs were found. Only 1 (MUU) triggered a full entry signal. It stopped out for -$92. The other 4 stretched but never reclaimed VWAP — correct behavior, the strategy sits out when the setup isn't there.

## Architecture
```
src/
  clients/     — tws_client.py, fetch.py, contracts.py, safety.py, scanner.py
  config/      — settings.py (Pydantic, loads from .env + YAML)
  strategy/    — setup_detector.py (stretch + reclaim), universe_filter.py, risk_gate.py
  indicators/  — rsi.py, vwap.py, gap.py
  execution/   — order_builder.py, order_submit.py, position_monitor.py, trade_manager.py
  storage/     — db.py (SQLite + WAL), repositories.py
  reporting/   — trade_logger.py (JSONL), daily_report.py (Markdown/CSV)
  jobs/        — scan_candidates.py, run_session.py
  utils/       — logging.py, time_utils.py
  cli.py       — Typer CLI
config/        — strategy.yaml, universe.yaml, risk.yaml, schedule.yaml, exclusions.yaml
tests/         — 53 unit tests
```

## Config Files
- `config/strategy.yaml` — gap threshold (5%), RSI (≤25), VWAP distance (≥0.5%), stop buffer (0.1%), target (2R)
- `config/risk.yaml` — $100/trade, $300/day, 1 max position, 3 max trades/day
- `config/schedule.yaml` — scan 6:00, active 6:30-8:00, flatten 12:45 (all PT)
- `config/exclusions.yaml` — leveraged ETF blocklist
- `.env` — IBKR connection (host, port, client_id)

## Sharing IB Gateway
This bot uses client ID 30. The momentum watcher uses client ID 20. Both connect to port 4002. No conflict — IB Gateway supports multiple client IDs.

## Tests
```bash
source .venv/bin/activate
pytest tests/ -v  # 53 tests
```

## Robin's Preferences
- Paper trading first, always
- Prefers `--dry-run` for data collection over live orders
- Wants autonomous operation — Claude handles details
- Never be pushy about missing info, ask once and wait
