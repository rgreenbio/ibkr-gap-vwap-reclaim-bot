#!/usr/bin/env bash
# Run the full intraday session via scanner (no watchlist needed).
# Uses --dry-run by default for data collection.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

mkdir -p outputs/logs

LOG="outputs/logs/session_$(date +%Y-%m-%d).log"

echo "$(date): Starting gap-vwap-bot session" >> "$LOG"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python -m src.cli run --dry-run >> "$LOG" 2>&1
EXIT_CODE=$?

echo "$(date): Session exited with code $EXIT_CODE" >> "$LOG"
