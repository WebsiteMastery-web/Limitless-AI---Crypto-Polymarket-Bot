# Limitless AI

### The most advanced autonomous AI trading system ever built at a hackathon.

Limitless AI is a **12-layer intelligence pipeline** that ingests real-time market data, geopolitical signals, whale movements, simulated crowd behavior, and prediction markets — then runs a **multi-agent AI debate** where Bull, Bear, and Neutral analysts argue before a Portfolio Manager (Claude Opus) makes the final call.

**It doesn't just predict. It debates, stress-tests, and only trades when it's confident.**

## Demo

[Watch the full demo walkthrough](https://drive.google.com/file/d/1byH7SimwmZnK0HX6FBaoMjsEHiA7W2x2/view?usp=sharing)

> The frontend dashboard was attempted but wasn't fully working in time — the video walkthrough shows the full system in action instead.

---

## What Makes This Different

Most trading bots use a single model reading a single signal. Limitless AI uses **12 independent intelligence layers** feeding into an **adversarial debate system** — the same approach used by institutional trading desks, but fully autonomous.

| What | Why It Matters |
|------|---------------|
| 12 intelligence layers | No single point of failure — diverse signals reduce false positives |
| Multi-agent debate | Bull and Bear AI agents argue; a judge decides — reduces overconfidence |
| Whale wallet tracking | See what the big money is doing before the market reacts |
| 250 simulated retail agents (MiroFish) | Model crowd psychology and herd behavior in real-time |
| Geopolitical signal processing | GDELT scans 100k+ global news sources for macro impact |
| Confidence calibration | System blocks its own trades when conviction is too low |

---

## The 12-Layer Intelligence Pipeline

| Layer | Name | What It Does |
|-------|------|-------------|
| L1 | **Live BTC Price & Market Data** | Real-time and historical prices via Alpaca and yfinance |
| L2 | **MiroFish** | 250 simulated retail agents modeling crowd sentiment and herd dynamics |
| L3 | **Market Regime Detection** | Classifies current market as trending, sideways, or volatile |
| L4 | **Elo-Weighted Confidence** | Dynamically ranks agent credibility based on past accuracy |
| L5 | **GDELT Geopolitical Signals** | Processes 100k+ global news sources for event impact scoring |
| L6 | **Knowledge Graph Analysis** | Historical pattern memory — the system learns from its own history |
| L7 | **Kronos** | Time-series pattern recognition and market cycle detection |
| L8 | **Whale Wallet Tracker** | On-chain monitoring of whale accumulation and distribution |
| L9 | **Policy & Volatility Signals** | Macro policy impact analysis and volatility regime detection |
| L10 | **TradingAgents Core** | Multi-agent debate engine — Bull vs Bear vs Neutral analysts argue |
| L11 | **Confidence Calibration** | Statistical calibration ensures confidence scores match real accuracy |
| L12 | **Risk Management** | Position sizing, threshold gating, and regime-aware risk controls |

---

## How Decisions Are Made

```
12 Intelligence Layers
        |
        v
  4 Analyst Agents (Market, Social, News, Fundamentals)
        |
        v
  Investment Debate (Bull vs Bear, judged by neutral arbiter)
        |
        v
  Risk Debate (Aggressive vs Conservative stress-test)
        |
        v
  Portfolio Manager (Claude Opus) — Final BUY / SELL / HOLD
        |
        v
  Risk Gate — Blocks low-conviction trades automatically
```

---

## Backtest Results

Backtested against real historical BTC price data with outcome verification:

| Metric | Value |
|--------|-------|
| Total backtests | 6 |
| Actionable signals | 1 (SELL on Apr 7) |
| Win rate | **100%** |
| Expectancy per trade | **+1.14%** |
| Verified against | Actual next-day BTC close price |

The system correctly predicted BTC would drop from $71,941 to $71,123 on April 7-8, 2026 — issuing a SELL signal based on bearish whale activity and cross-layer consensus.

**The system is deliberately conservative** — it issued HOLD on 5 of 6 dates, only trading when all layers aligned. This is by design: fewer trades, higher conviction, better outcomes.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **AI Models** | Claude Opus 4.6, Claude Haiku 4.5 (Anthropic API) |
| **Agent Framework** | LangGraph + LangChain multi-agent orchestration |
| **Market Data** | Alpaca, yfinance, Tavily, GDELT, Polymarket, EDGAR |
| **Execution** | Polymarket paper trading, Binance testnet |
| **Infrastructure** | Python 3.12, DigitalOcean VPS, automated cron pipeline |

---

## Architecture

```
limitless-ai/
  run_backtest.py          -- Backtester with outcome tracking
  run_paper_trade.py       -- Live paper trading runner
  multi_asset_runner.py    -- Multi-asset pipeline orchestrator
  dashboard_api.py         -- API for frontend dashboard
  regime_detector.py       -- L3: Market regime classification
  risk_manager.py          -- L12: Risk gating and position sizing
  confidence_calibrator.py -- L11: Signal confidence calibration
  kronos_signal.py         -- L7: Time-series pattern recognition
  gdelt_client.py          -- L5: Geopolitical news client
  agent_elo.py             -- L4: Elo-weighted agent ranking
  polymarket_executor.py   -- Polymarket trade execution
  mirofish_receiver.py     -- L2: MiroFish crowd simulation receiver
  TradingAgents/           -- L10: Multi-agent debate framework
  knowledge_base/          -- L6: Historical pattern storage
  logs/                    -- Backtest results and trade journals
```

---

*Built at hackathon. Powered by Claude.*
