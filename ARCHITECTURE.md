# Limitless AI - Architecture

## Risk Manager (risk_manager.py)

All trade signals pass through 8 sequential checks before execution:

| Check | Rule |
|-------|------|
| min_confidence | >= 65% (volatility-scaled up to 80%) |
| max_drawdown | <= 10% from peak equity |
| daily_trade_limit | <= 5 trades/day |
| post_loss_cooldown | 4h block after any loss |
| consecutive_loss_breaker | 24h block after 3 consecutive losses |
| volatility_confidence | Higher vol -> higher confidence required |
| market_regime | BTC vs 20-SMA gate for BUY signals |
| alpaca_connectivity | Account must be ACTIVE |

stop_loss_pct: Dynamic ATR-based (2xATR, clamped 1.5%-5%, fallback 3.0%)

Position sizing: Kelly fraction capped at 10% of equity.

## Data Flows

- alpaca_feed.py: OHLCV, live price, paper balance, ATR calculation
- yfinance: Volatility, SMA20, ATR (4h bars, 30-day lookback)

## Execution

- alpaca_executor.py: Paper trade placement, trade JSON logging
- run_paper_trade.py: Full pipeline: price -> agents -> risk -> execute
- Trailing stop logged per trade as trailing_stop_pct in trade JSON

## Agents

- TradingAgentsGraph: Multi-agent analysis pipeline (2-5 min)
- MiroFish: Optional sentiment overlay from Windows PC
