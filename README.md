# Limitless AI - Crypto and Polymarket Trading Bot

An autonomous multi-agent AI trading system that analyzes BTC-USD and Polymarket using a 9-layer intelligence pipeline with debate-driven decision making.

> **Note:** I attempted to build the frontend dashboard with Claude, but it was not fully working in time, so I made a video walkthrough explaining how the system actually works end-to-end instead.

## How It Works

The system runs a **9-layer intelligence pipeline** that feeds into a multi-agent debate framework:

1. **Price Data** - Real-time and historical BTC prices via Alpaca and yfinance
2. **News Analysis** - Global crypto news from Tavily with sentiment scoring
3. **Whale Tracking** - On-chain whale activity detection (distribution/accumulation)
4. **Options Flow** - Put/Call ratio analysis for institutional positioning
5. **Congressional/Insider Trades** - EDGAR filings for insider signals
6. **Polymarket Signals** - Prediction market data for macro sentiment
7. **Geopolitical Analysis** - GDELT-powered global event impact scoring
8. **Knowledge Base** - Historical pattern memory for context
9. **Regime Detection** - Market regime classification (trending/sideways/volatile)

### Multi-Agent Decision Engine

After gathering intelligence, a **TradingAgents** framework runs:

- **4 Analyst Agents** (Market, Social, News, Fundamentals) each produce independent reports
- **Investment Debate** - Bull vs Bear agents argue, a judge synthesizes
- **Risk Debate** - Aggressive vs Conservative agents stress-test the plan
- **Portfolio Manager** (Claude Opus) - Makes the final BUY/SELL/HOLD decision with conviction rating

### Backtesting

The system backtests against historical data, checking decisions against actual next-day price movement:

- Total backtests: 6
- Actionable signals: 1 (SELL)
- Win rate: 100%
- Expectancy per trade: +1.14%

### Risk Management

- Confidence threshold gating (blocks low-conviction trades)
- Volatility-adjusted position sizing
- Regime-aware risk multipliers
- Paper trading mode for validation

## Tech Stack

- **LLMs**: Claude Opus 4.6, Claude Haiku 4.5 (via Anthropic API)
- **Framework**: LangGraph + LangChain multi-agent orchestration
- **Data**: Alpaca, yfinance, Tavily, GDELT, Polymarket, EDGAR
- **Execution**: Polymarket paper trading, Binance testnet
- **Infra**: Python 3.12, running on DigitalOcean VPS with cron automation

## Project Structure

- run_backtest.py - Backtester with outcome tracking
- run_paper_trade.py - Live paper trading runner
- multi_asset_runner.py - Multi-asset pipeline orchestrator
- dashboard_api.py - API for frontend dashboard
- regime_detector.py - Market regime classification
- risk_manager.py - Risk gating and position sizing
- confidence_calibrator.py - Signal confidence scoring
- kronos_signal.py - Macro timing signal
- gdelt_client.py - Geopolitical news client
- polymarket_executor.py - Polymarket trade execution
- TradingAgents/ - Multi-agent debate framework
- logs/ - Backtest results and summaries
