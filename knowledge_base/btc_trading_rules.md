# BTC Trading Rules - Limitless AI
*Static rules file - do not update via cron*
*Source: Project configuration*

## Position Sizing Rules
- Maximum single position: 10% of available cash (15% for STRONG_BUY signals)
- Never go all-in: Maximum 50% of portfolio in BTC at any time
- Minimum trade size: $100 USD equivalent

## Risk Rules
- Stop-loss: 5% below entry price for BUY, 5% above for SELL
- Take-profit target: 15% gain minimum before considering exit
- Maximum daily trades: 5 (prevents overtrading)
- Cooldown after loss: 4 hours before next trade allowed
- Max drawdown before pause: 10% of starting capital

## Signal Consensus Rules
- BUY requires: 3+ bullish signals AND confidence >= 72%
- SELL requires: 3+ bearish signals AND confidence >= 72%  
- STRONG signals (5+ aligned): position size increases to 15%
- HOLD is default when signals are mixed or inconclusive

## Time Rules
- Preferred trading hours: 08:00-22:00 UTC (higher Alpaca liquidity)
- Avoid: 02:00-05:00 UTC (lowest crypto volume)
- No trades within 30 minutes of major macro events (Fed announcements etc.)

## Paper Trading Phase Rules
- All trades are PAPER only until 200 completed trades with >55% win rate
- Win rate = closed profitable trades / total closed trades
- Track P&L weekly, review strategy monthly
