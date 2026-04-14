# Limitless AI - Crypto and Polymarket Trading Bot

An autonomous multi-agent AI trading system that analyzes BTC-USD and Polymarket using a 12-layer intelligence pipeline with debate-driven decision making.

> **Note:** I attempted to build the frontend dashboard with Claude, but it was not fully working in time, so I made a video walkthrough explaining how the system actually works end-to-end instead.
## Demo Video

[Watch the full demo walkthrough on Google Drive](https://drive.google.com/file/d/1byH7SimwmZnK0HX6FBaoMjsEHiA7W2x2/view?usp=sharing)


## How It Works

The system runs a **12-layer intelligence pipeline** that feeds into a multi-agent debate framework:

1. **L1: Live BTC Price and Market Data** - Real-time and historical prices via Alpaca and yfinance
2. **L2: MiroFish** - 250 simulated retail agents modeling crowd sentiment
3. **L3: Market Regime Detection** - Classification of trending/sideways/volatile regimes
4. **L4: Elo-Weighted Confidence Scoring** - Dynamic agent credibility ranking
5. **L5: GDELT Geopolitical News Signals** - Global event impact scoring from 100k+ sources
6. **L6: Knowledge Graph Analysis** - Historical pattern memory and context retrieval
7. **L7: Kronos** - Time-series pattern recognition and cycle detection
8. **L8: Whale Wallet Movement Tracker** - On-chain whale accumulation/distribution signals
9. **L9: Policy and Volatility Signals** - Macro policy impact and vol regime analysis
10. **L10: TradingAgents Core Framework** - Multi-agent debate engine (Bull vs Bear vs Neutral)
11. **L11: Confidence Calibration** - Statistical calibration of signal confidence scores
12. **L12: Risk Management** - Position sizing, threshold gating, and regime-aware risk controls

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
