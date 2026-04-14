"""
Limitless AI — Geopolitical Causal Chain Agent
Reads current headlines and reasons about BTC market impact using
baked-in historical event patterns. Returns structured signal.
"""
import os
import json
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv('/root/limitless-ai/TradingAgents/.env')

# --- Historical knowledge base baked into the prompt ---
# This is the seed knowledge. Over time, OpenClaw memory expands this.
GEOPOLITICAL_KNOWLEDGE = """
HISTORICAL GEOPOLITICAL EVENT -> CRYPTO MARKET IMPACT PATTERNS:

OIL & ENERGY SHOCKS:
- Middle East conflict escalation → oil spike → macro risk-off → BTC sells off 5-15% within 48h
- OPEC production cuts → oil spike → inflation fears → Fed hawkish → BTC bearish
- US sanctions on oil exporters → short-term BTC rally (dollar weakness narrative)

FED & MONETARY POLICY:
- Fed rate hike surprise → BTC drops 8-20% same day
- Fed pause or pivot signal → BTC rallies 10-30% within days
- CPI higher than expected → BTC drops (inflation fears, rate hike risk)
- CPI lower than expected → BTC rallies (rate cut hopes)

BANKING & FINANCIAL CRISES:
- Bank failure/contagion fears → BTC short-term drop then rally (flight from banks)
- SVB-style collapses → BTC initially drops then recovers above pre-crisis level
- Dollar weakness prolonged → BTC bullish (store of value narrative)

REGULATORY:
- US crypto regulation crackdown news → BTC drops 10-25%
- ETF approval or major institutional adoption → BTC rallies 15-40%
- Country banning crypto → short-term drop, recovers within weeks
- Country adopting crypto as legal tender → BTC rallies

GEOPOLITICAL CONFLICTS:
- US-China trade war escalation → risk-off, BTC drops
- US-China trade war de-escalation or deal → risk-on, BTC rallies
- Russia-Ukraine conflict escalation → initial BTC drop, then gold/BTC rally
- Taiwan strait tensions rising → BTC drops with equities

MACRO RISK SENTIMENT:
- VIX spike above 30 → BTC drops with equities
- Stock market crash → BTC drops in correlation, sometimes leads recovery
- Dollar index (DXY) rising → BTC bearish (inverse correlation)
- Dollar index falling → BTC bullish

CONGRESSIONAL/INSIDER SIGNALS:
- Senators buying tech/crypto ETFs before regulation news → bullish signal
- Mass insider selling in crypto-adjacent companies → bearish signal
"""

SYSTEM_PROMPT = f"""You are the Geopolitical Causal Chain Analyst for Limitless AI, an autonomous BTC trading system.

Your job: given current news headlines, identify geopolitical and macro events, then reason through their likely impact on BTC price using established historical patterns.

{GEOPOLITICAL_KNOWLEDGE}

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown, no explanation outside the JSON:
{{
  "geopolitical_events": [
    {{
      "event": "brief description",
      "category": "OIL|FED|BANKING|REGULATORY|CONFLICT|MACRO|CONGRESSIONAL",
      "direction": "BULLISH|BEARISH|NEUTRAL",
      "confidence": 0-100,
      "causal_chain": "event X → because Y → BTC impact Z",
      "timeframe": "IMMEDIATE|24H|1WEEK|MONTH"
    }}
  ],
  "aggregate_signal": "BULLISH|BEARISH|NEUTRAL",
  "aggregate_confidence": 0-100,
  "reasoning": "1-2 sentence summary of dominant forces"
}}

If no geopolitical events are relevant to BTC, return aggregate_signal NEUTRAL with confidence 30.
"""


def get_geopolitical_signal(headlines: str) -> dict:
    """
    Given a string of current news headlines, return geopolitical causal chain analysis.
    """
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
    if not anthropic_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping geopolitical analysis")
        return {"aggregate_signal": "NEUTRAL", "aggregate_confidence": 30,
                "reasoning": "No API key", "geopolitical_events": []}

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {anthropic_key}",
                "content-type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat",
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Current headlines:\n{headlines}"}
                ]
            },
            timeout=30
        )
        resp.raise_for_status()
        resp_json = resp.json()
        # Handle both OpenRouter and standard OpenAI response formats
        try:
            content = resp_json["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            # Fallback: try to find content anywhere in response
            if "content" in str(resp_json):
                import re
                match = re.search(r'"content":\s*"([^"]+)"', str(resp_json))
                if match:
                    content = match.group(1)
                else:
                    raise ValueError(f"Could not parse response: {str(resp_json)[:200]}")
            else:
                raise ValueError(f"No content in response: {str(resp_json)[:200]}")

        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = json.loads(content)
        logger.info(f"Geopolitical signal: {result.get('aggregate_signal')} "
                    f"({result.get('aggregate_confidence')}%) — {result.get('reasoning','')[:80]}")
        return result

    except Exception as e:
        logger.warning(f"Geopolitical analysis failed: {e}")
        return {"aggregate_signal": "NEUTRAL", "aggregate_confidence": 30,
                "reasoning": f"Analysis error: {e}", "geopolitical_events": []}


def get_geopolitical_signal_from_tavily() -> dict:
    """
    Fetch live macro headlines via Tavily and run geopolitical analysis.
    Called automatically during pipeline runs.
    """
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        return {"aggregate_signal": "NEUTRAL", "aggregate_confidence": 30,
                "reasoning": "No Tavily key", "geopolitical_events": []}

    queries = [
        "geopolitical crisis market impact today",
        "Federal Reserve interest rates inflation 2026",
        "US China trade war tariffs",
        "Middle East oil energy crisis",
        "crypto regulation SEC bitcoin ETF"
    ]

    headlines = []
    for q in queries:
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily_key, "query": q, "max_results": 2,
                      "search_depth": "basic"},
                timeout=10
            )
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    headlines.append(f"- {item.get('title','')} | {item.get('content','')[:150]}")
        except Exception:
            pass

    if not headlines:
        return {"aggregate_signal": "NEUTRAL", "aggregate_confidence": 30,
                "reasoning": "No headlines fetched", "geopolitical_events": []}

    headlines_str = "\n".join(headlines[:10])
    logger.info(f"Geopolitical: fetched {len(headlines)} headlines for analysis")
    return get_geopolitical_signal(headlines_str)
