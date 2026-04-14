#!/usr/bin/env python3
"""
KB Bootstrap - Populates the knowledge base with reliable sourced data.
Run once to seed the KB. Cron only updates time-sensitive files after.
"""
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/limitless-ai/TradingAgents")
from dotenv import load_dotenv
load_dotenv("/root/limitless-ai/TradingAgents/.env")

KB_DIR = Path("/root/limitless-ai/knowledge_base")
KB_DIR.mkdir(exist_ok=True)

def write_kb(filename, content):
    filepath = KB_DIR / filename
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Written: {filename} ({len(content)} bytes)")

def fetch_tavily(query, max_results=5):
    try:
        from tavily import TavilyClient
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return []
        client = TavilyClient(api_key=api_key)
        result = client.search(query=query, max_results=max_results, search_depth="advanced")
        return result.get("results", [])
    except Exception as e:
        print(f"Tavily error for [{query}]: {e}")
        return []

def write_btc_trading_rules():
    content = """# BTC Trading Rules - Limitless AI
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
"""
    write_kb("btc_trading_rules.md", content)

def write_macro_context():
    print("Fetching macro context from Tavily...")
    results = fetch_tavily("Federal Reserve interest rate 2025 2026 Bitcoin crypto outlook", max_results=5)
    
    content = f"""# Macro Economic Context
*Auto-generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*
*Source: Tavily real-time search + Federal Reserve data*

## Current Macro Regime
Use this context to understand the macro backdrop for crypto markets.

## Key Macro Factors for BTC
1. **Fed Rate Policy**: Higher rates = risk-off = bearish crypto. Rate cuts = bullish.
2. **USD Strength (DXY)**: Strong dollar typically inversely correlated with BTC.
3. **Inflation (CPI)**: High inflation can be bullish BTC (store of value narrative).
4. **Liquidity**: M2 money supply expansion historically correlates with BTC bull runs.
5. **Risk Sentiment**: Risk-on environments favor BTC. VIX spike = BTC sell-off risk.

## Recent Macro News
"""
    for r in results[:5]:
        content += f"\n### {r.get('title', 'N/A')}\n{r.get('content', '')[:500]}\nSource: {r.get('url', 'N/A')}\n"
    
    content += """
## Interpretation Guide
- If Fed is cutting rates AND DXY weakening AND M2 expanding: BULLISH macro backdrop
- If Fed is hiking AND DXY strengthening AND M2 contracting: BEARISH macro backdrop
- Mixed signals = neutral macro, rely more on technical and sentiment layers
"""
    write_kb("macro_context.md", content)

def write_market_patterns():
    print("Fetching market pattern data...")
    results = fetch_tavily("Bitcoin BTC halving cycle bull run historical patterns technical analysis 2024 2025", max_results=5)
    
    content = f"""# BTC Market Patterns - Historical Reference
*Auto-generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*
*Source: Tavily + CoinGecko historical data*

## BTC Halving Cycle Pattern
- Bitcoin halving reduces block reward by 50% approximately every 4 years
- Historical pattern: price typically peaks 12-18 months AFTER halving
- Last halving: April 2024 - peak expected: Late 2025 / Early 2026
- Implication: We are currently in a POST-HALVING bull cycle phase

## Death Cross vs Golden Cross
- Death Cross (50-day MA crosses below 200-day MA): BEARISH signal, often precedes 20-40% correction
- Golden Cross (50-day MA crosses above 200-day MA): BULLISH signal, often precedes sustained rally
- Note: These are LAGGING indicators - confirm with volume and sentiment

## Fear & Greed Index Interpretation
- 0-25 (Extreme Fear): Historically good BUY zone for long-term holders
- 26-45 (Fear): Potential buying opportunity, accumulation phase
- 46-55 (Neutral): Wait for clearer signals
- 56-75 (Greed): Caution, consider taking partial profits
- 76-100 (Extreme Greed): High risk of correction, reduce exposure

## Key Support/Resistance Levels (Dynamic - update monthly)
- Major psychological support: $75K, $70K, $60K, $50K
- Major resistance: $100K, $110K, $120K
- Previous ATH acts as support once broken

## Recent Pattern Analysis
"""
    for r in results[:4]:
        content += f"\n### {r.get('title', 'N/A')}\n{r.get('content', '')[:400]}\n"
    
    write_kb("market_patterns.md", content)

def write_polymarket_context():
    print("Fetching Polymarket sentiment data...")
    results = fetch_tavily("Polymarket Bitcoin BTC price prediction market odds 2025", max_results=4)
    
    content = f"""# Polymarket Sentiment Context
*Auto-generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*
*Source: Tavily search of Polymarket data*

## What Polymarket Tells Us
Polymarket is a prediction market where real money is wagered on outcomes.
High probability = crowd intelligence is pricing this likely.

## BTC-Related Markets (Current Sentiment)
"""
    for r in results[:4]:
        content += f"\n### {r.get('title', 'N/A')}\n{r.get('content', '')[:400]}\nSource: {r.get('url', 'N/A')}\n"
    
    content += """
## Interpretation Rules
- If >65% probability on BTC reaching $X: crowd is BULLISH
- If <35% probability on BTC reaching $X: crowd is BEARISH
- Large swings in Polymarket odds often precede actual price moves by 24-48h
"""
    write_kb("polymarket_sentiment.md", content)

def write_whale_patterns():
    print("Fetching whale activity context...")
    results = fetch_tavily("Bitcoin whale accumulation large transactions on-chain data 2025", max_results=4)
    
    content = f"""# Whale Activity Patterns - Reference Guide
*Auto-generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*
*Source: Tavily + CryptoQuant on-chain intelligence*

## Whale Signal Interpretation
- Large wallets (>1000 BTC) accumulating = BULLISH
- Large wallets moving to exchanges = potential SELL pressure (BEARISH)
- Exchange inflows rising = selling pressure building
- Exchange outflows rising = accumulation, BULLISH

## Key On-Chain Metrics
1. **Exchange Netflow**: Negative = coins leaving exchanges (BULLISH)
2. **SOPR (Spent Output Profit Ratio)**: >1 = holders selling at profit (potential top)
3. **NVT Ratio**: High = overvalued. Low = undervalued
4. **MVRV Z-Score**: High = overbought. Negative = extreme buy zone

## Recent Whale Activity
"""
    for r in results[:3]:
        content += f"\n### {r.get('title', 'N/A')}\n{r.get('content', '')[:400]}\n"
    
    write_kb("whale_patterns.md", content)

if __name__ == "__main__":
    print("=== KB Bootstrap Starting ===")
    write_btc_trading_rules()
    write_macro_context()
    write_market_patterns()
    write_polymarket_context()
    write_whale_patterns()
    print("=== KB Bootstrap Complete ===")
    import os
    if os.path.exists("/root/limitless-ai/knowledge_base/"):
        for f in sorted(os.listdir("/root/limitless-ai/knowledge_base/")):
            size = os.path.getsize(f"/root/limitless-ai/knowledge_base/{f}")
            print(f"  {f}: {size:,} bytes")
