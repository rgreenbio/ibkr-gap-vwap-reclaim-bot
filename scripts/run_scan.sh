#!/bin/bash
# Scheduled gap-vwap bot session
# Usage: ./run_scan.sh

KILL_SWITCH="$HOME/.ibkr_kill_switch"
if [ -f "$KILL_SWITCH" ]; then
    echo "$(date): GLOBAL KILL SWITCH active — skipping gap-vwap bot" >> "$HOME/.ibkr_kill_switch.log"
    exit 0
fi

PROJECT_DIR="/Users/robin/Documents/GitHub/ibkr-gap-vwap-reclaim-bot"

if [ -f "$PROJECT_DIR/.kill_switch" ]; then
    echo "$(date): REPO KILL SWITCH active — skipping gap-vwap bot" >> "$HOME/.ibkr_kill_switch.log"
    exit 0
fi
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/outputs/logs"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)
LOG_FILE="$LOG_DIR/session_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

echo "=== Gap-VWAP Bot ===" > "$LOG_FILE"
echo "Started: $(date)" >> "$LOG_FILE"

cd "$PROJECT_DIR"
OUTPUT=$($PYTHON -m src.cli run --dry-run 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" >> "$LOG_FILE"
echo "Exit code: $EXIT_CODE" >> "$LOG_FILE"
echo "Finished: $(date)" >> "$LOG_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    osascript -e "display notification \"Gap-VWAP scan complete\" with title \"Gap-VWAP Bot\" sound name \"Glass\"" 2>/dev/null
else
    osascript -e "display notification \"Gap-VWAP scan failed (exit $EXIT_CODE)\" with title \"Gap-VWAP Bot\" sound name \"Basso\"" 2>/dev/null
fi

exit $EXIT_CODE
