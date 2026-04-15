# Limitless AI — Multi-Agent Financial Intelligence System

> Built solo. 17 years old. Buenos Aires. — *Kaszek × Anthropic Hackathon, April 14 2026*

**Demo:** [Watch full system walkthrough](https://drive.google.com/file/d/1byH7SimwmZnK0HX6FBaoMjsEHiA7W2x2/view?usp=sharing)

---

## Built for the gap Brad Abrams described

During his keynote at Digital House, Brad Abrams (Anthropic) said the use cases Anthropic is most excited about are where **Claude fills a gap humans genuinely can't** — naming finance as the prime example.

This is that use case.

A professional analyst can track 3–4 signals at once. BTC price reacts to whale movements, congressional insider trades, geopolitical shocks, retail crowd psychology, prediction market probabilities, and volatility regime shifts — **simultaneously, in real time**. No human can synthesize 12 independent signal streams, run an adversarial debate across them, and act in minutes — without bias, without fatigue, every hour.

Limitless AI does exactly that. Claude Opus isn't a chatbot here. It's a Portfolio Manager operating at a cognitive bandwidth no human analyst can match.

---

## What Limitless AI Does

A 12-layer intelligence pipeline ingests live market data, on-chain whale flows, GDELT geopolitical signals, simulated retail crowd behavior, congressional stock filings (EDGAR), and Polymarket prediction probabilities — in parallel.

Then it runs an **adversarial AI debate** where Bull, Bear, and Neutral analysts argue. A neutral arbiter judges. The result goes to a **Claude Opus Portfolio Manager** that synthesizes everything into a final BUY / SELL / HOLD decision.

If confidence falls below threshold: the system blocks its own trade.

**It doesn't just predict. It debates, stress-tests, and only acts when it's certain.**

---

## The 12 Intelligence Layers

| Layer | Signal | What It Contributes |
|-------|--------|-------------------|
| L1 | Live Market Data | Real-time BTC price, volume, order book via Alpaca + yfinance |
| L2 | MiroFish | 250 simulated retail agents model crowd sentiment and herd behavior (local Mistral 7B) |
| L3 | Market Regime Detection | Classifies market as trending, sideways, or volatile — context for all downstream layers |
| L4 | Elo-Weighted Agent Ranking | Re-weights agent credibility by past accuracy — wrong agents lose influence automatically |
| L5 | GDELT Geopolitical Signals | Processes 100,000+ global news sources for macro event impact scoring |
| L6 | Knowledge Graph | Historical pattern memory — the system learns from its own prior decisions |
| L7 | Kronos | Time-series pattern recognition and market cycle detection |
| L8 | Whale Wallet Tracker | On-chain monitoring of large wallet accumulation and distribution |
| L9 | Policy & Volatility Signals | Macro policy analysis + volatility regime detection |
| L10 | TradingAgents Debate Engine | Bull vs Bear vs Neutral analysts argue in structured multi-agent debate |
| L11 | Confidence Calibration | Ensures confidence scores match real historical accuracy |
| L12 | Risk Management | Position sizing, threshold gating, regime-aware controls |

---

## Decision Architecture

```
12 Signal Layers (parallel execution)
            │
            ▼
4 Analyst Agents — Market · Social · News · Fundamentals
            │
            ▼
Investment Debate — Bull vs Bear, judged by neutral arbiter
            │
            ▼
Risk Debate — Aggressive vs Conservative stress-test
            │
            ▼
Portfolio Manager (Claude Opus 4.6) — Final BUY / SELL / HOLD
            │
            ▼
Risk Gate — Blocks any trade below conviction threshold
```

---

## Results

Backtested against real historical BTC-USD price data (Mar 17 – Apr 11, 2026) with next-day outcome verification:

| Metric | Result |
|--------|--------|
| Historical dates analyzed | 6 |
| Trade signals issued | 1 |
| That signal correct | **Yes (+1.14%)** |
| Dates where system held | 5 of 6 |

**Apr 7, 2026:** System issued SELL at $71,941 based on bearish whale activity and cross-layer consensus. BTC closed at $71,123 the next day. ✓

5 of 6 dates returned HOLD. That's the design — the system only acts when every layer agrees. It would rather miss a move than make a wrong one.

---

## Ethical Alignment

Safety isn't a feature. It's structural:

- **Paper trading only** — no real capital at risk until statistical validation is complete
- **Confidence gating** — the system can and does say "I don't know" and blocks itself
- **Full audit trail** — every decision logged with full reasoning; every debate stored
- **Transparent decision chain** — the Bull vs Bear argument is readable by the operator at any time; no black box
- **Elo re-weighting** — agents that are wrong repeatedly lose influence systematically
- **No position size manipulation** — capped sizing, no wash trading, no spoofing

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Models | Claude Opus 4.6 (Portfolio Manager), Claude Haiku 4.5 (debate agents) |
| Local AI | Mistral 7B (MiroFish crowd simulation — runs on-device, no API cost) |
| Agent Framework | LangGraph + LangChain multi-agent orchestration |
| Market Data | Alpaca, yfinance, Tavily, GDELT, Polymarket, EDGAR |
| Execution | Polymarket paper trading, Binance testnet |
| Infrastructure | Python 3.12, DigitalOcean VPS, automated hourly cron pipeline |

---

## Architecture

```
limitless-ai/
├── run_paper_trade.py        — Live paper trading runner
├── run_backtest.py           — Backtester with outcome verification
├── multi_asset_runner.py     — Multi-asset pipeline orchestrator
├── performance_tracker.py    — PnL and Sharpe tracking
├── regime_detector.py        — L3: Market regime classification
├── risk_manager.py           — L12: Risk gating and position sizing
├── confidence_calibrator.py  — L11: Confidence calibration
├── kronos_signal.py          — L7: Time-series pattern recognition
├── gdelt_client.py           — L5: Geopolitical news client
├── agent_elo.py              — L4: Elo-weighted agent ranking
├── polymarket_executor.py    — Polymarket paper trade execution
├── mirofish_receiver.py      — L2: MiroFish crowd simulation receiver
├── TradingAgents/            — L10: Multi-agent debate framework
├── knowledge_base/           — L6: Historical pattern storage
└── logs/                     — Pipeline runs, debates, trade journals
```

---

*Built at the Kaszek × Anthropic Hackathon, Buenos Aires, April 14 2026. Powered by Claude.*
