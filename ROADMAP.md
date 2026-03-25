# Roadmap

## V1 — Current (Paper Trading Foundation)

- [x] Rule-driven gap-down VWAP reclaim strategy
- [x] IBKR paper trading integration via ib_insync
- [x] Configurable universe, strategy, risk, and schedule
- [x] SQLite persistence with full trade lifecycle tracking
- [x] Bracket order execution (entry + stop + target)
- [x] Hard risk controls (per-trade, daily, position limits)
- [x] Session time enforcement (entry window, flatten deadline)
- [x] Per-ticker JSONL event logging
- [x] Markdown/CSV daily reports
- [x] CLI with scan, run, report, status commands
- [x] Deterministic unit tests for pure strategy logic

## V1.1 — Data Quality & Reliability

- [ ] IBKR scanner integration (replace manual watchlist)
- [ ] Reconnection handling for dropped TWS connections
- [ ] Premarket volume scanner using IBKR scanners
- [ ] Gap scanner using IBKR market scanners
- [ ] Spread sanity check before entry

## V2 — Additional Entry Patterns

- [ ] Opening range breakout variant
- [ ] Red-to-green move trigger
- [ ] Volume surge confirmation layer
- [ ] Multi-timeframe RSI confirmation

## V3 — Dynamic Exit Management

- [ ] Trailing stop after 1R profit
- [ ] Partial exits (half at 1R, half at 2R)
- [ ] Time-based stop tightening
- [ ] Momentum-based exit (RSI overbought)

## V4 — Context & Filtering

- [ ] Sector/industry awareness
- [ ] Market regime filter (VIX-based)
- [ ] Relative strength vs sector
- [ ] Simple headline classifier for catastrophic news
- [ ] Offering/dilution detection

## V5 — Analysis & Optimization

- [ ] RRS (Reversal Readiness Score) as ranking/gating layer
- [ ] Backtest/replay harness using historical data
- [ ] MFE/MAE analysis dashboard
- [ ] Win rate by gap size, sector, time of day
- [ ] Position sizing optimization

## V6 — Multi-Position & Scale

- [ ] Multiple simultaneous positions (configurable limit)
- [ ] Priority ranking when multiple candidates trigger
- [ ] Portfolio-level risk management
- [ ] Correlation-aware position limits

## V7 — Dashboard & Monitoring

- [ ] Streamlit or web dashboard
- [ ] Real-time position monitoring
- [ ] Alert system (Slack/email on fills, stops, errors)
- [ ] Historical performance charts

## Future Considerations

- Live trading (requires thorough paper validation first)
- Short-side setups
- Options-based entries
- Intraday machine learning features (not in decision loop)
