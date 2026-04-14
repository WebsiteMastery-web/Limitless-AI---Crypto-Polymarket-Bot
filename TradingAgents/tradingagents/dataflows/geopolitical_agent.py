"""
Limitless AI — Geopolitical Causal Chain Agent
Searches for active geopolitical events and builds explicit BTC impact chains.
Knowledge base loaded from /root/limitless-ai/knowledge_base/
"""
import os
import requests
from loguru import logger

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
KB_PATH = "/root/limitless-ai/knowledge_base/geopolitical_btc_history.md"

GEOPOLITICAL_QUERIES = [
    "geopolitical crisis conflict war 2026",
    "US China trade war tariffs sanctions 2026",
    "Fed Federal Reserve interest rate decision 2026",
    "oil price OPEC supply shock 2026",
    "crypto regulation ban government 2026",
    "US dollar inflation CPI economic data 2026",
    "banking crisis financial system stress 2026",
    "Bitcoin ETF SEC regulation approval 2026",
]


def load_knowledge_base() -> str:
    """Load historical geopolitical-BTC impact knowledge base."""
    try:
        with open(KB_PATH) as f:
            return f.read()
    except Exception:
        return ""


def search_geopolitical_events() -> list[dict]:
    """Search Tavily for active geopolitical events relevant to BTC."""
    if not TAVILY_API_KEY:
        logger.warning("No Tavily key — skipping geopolitical search")
        return []

    results = []
    # Use first 3 queries to stay within token budget
    for query in GEOPOLITICAL_QUERIES[:3]:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": 2,
                    "search_depth": "basic",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for r in data.get("results", []):
                    results.append({
                        "query": query,
                        "title": r.get("title", ""),
                        "snippet": r.get("content", "")[:300],
                        "url": r.get("url", ""),
                    })
        except Exception as e:
            logger.warning(f"Geopolitical search error for '{query}': {e}")

    logger.info(f"Geopolitical agent: {len(results)} events found")
    return results


def build_geopolitical_context() -> str:
    """
    Build a structured geopolitical context string for injection into
    the news analyst prompt. Includes live events + historical patterns.
    """
    kb = load_knowledge_base()
    events = search_geopolitical_events()

    lines = ["=== GEOPOLITICAL INTELLIGENCE LAYER ===\n"]

    if events:
        lines.append("## ACTIVE GEOPOLITICAL SIGNALS (live search)\n")
        for ev in events:
            lines.append(f"### {ev['title']}")
            lines.append(f"Context: {ev['snippet']}")
            lines.append(f"Query trigger: {ev['query']}\n")

    lines.append("\n## CAUSAL CHAIN INSTRUCTIONS")
    lines.append(
        "For each active event above, build an explicit causal chain:\n"
        "EVENT → MECHANISM → BTC PRICE IMPACT (direction: BULLISH/BEARISH/NEUTRAL, "
        "magnitude: low/medium/high, timeframe: hours/days/weeks)\n"
        "Cross-reference against the historical patterns below.\n"
    )

    if kb:
        lines.append("\n## HISTORICAL GEOPOLITICAL-BTC PATTERNS (knowledge base)\n")
        # Include the most relevant sections
        lines.append(kb[:3000])  # Cap at 3000 chars to stay within context

    return "\n".join(lines)


def get_geopolitical_signals() -> str:
    """Entry point called by the pipeline."""
    try:
        context = build_geopolitical_context()
        logger.info("Geopolitical layer: context built successfully")
        return context
    except Exception as e:
        logger.warning(f"Geopolitical layer failed: {e}")
        return "Geopolitical layer unavailable."
