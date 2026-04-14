"""
Tavily News + Intelligence Layers — Limitless AI
Assembles all signal layers into global news context for the analyst agents.
Layers: Tavily News, SEC EDGAR, Polymarket, Geopolitical, Google Trends,
        Whale Tracker, Options Flow, Pattern Memory, Knowledge Base
"""
import os
import requests
from datetime import datetime, timedelta
from loguru import logger

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def get_news_tavily(ticker: str, num_articles: int = 3, curr_date: str = None) -> str:
    """Fetch recent news for a specific ticker/asset."""
    try:
        query = f"{ticker} price cryptocurrency news latest"
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query,
                  "max_results": num_articles, "search_depth": "basic"},
            timeout=15
        )
        if r.status_code != 200:
            return f"Tavily news unavailable (HTTP {r.status_code})"
        data = r.json()
        results = data.get("results", [])
        if not results:
            return f"No recent news found for {ticker}"
        output = f"=== LATEST NEWS FOR {ticker} ===\n"
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content_snip = result.get("content", "")[:300]
            published = result.get("published_date", "")
            output += f"\n[{i}] {title}\n"
            if published:
                output += f"    Published: {published}\n"
            output += f"    {content_snip}...\n"
            output += f"    Source: {url}\n"
        logger.info(f"Tavily news fetched for {ticker}: {len(results)} articles")
        return output
    except Exception as e:
        logger.warning(f"Tavily news failed for {ticker}: {e}")
        return f"Tavily news unavailable: {e}"


def get_global_news_tavily(ticker: str = "BTC-USD", num_articles: int = 5, curr_date: str = None) -> str:
    """Fetch global macro news + all intelligence layers."""
    output = ""

    # --- Layer 1: Tavily Global Macro News ---
    try:
        query = "global economy cryptocurrency bitcoin market news fed interest rates"
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query,
                  "max_results": num_articles, "search_depth": "basic"},
            timeout=15
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            output = f"=== GLOBAL MACRO NEWS ({len(results)} articles) ===\n"
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                content_snip = result.get("content", "")[:250]
                output += f"\n[{i}] {title}\n    {content_snip}...\n"
            logger.info(f"Tavily global news fetched: {len(results)} articles")
        else:
            output = "Global macro news unavailable."
    except Exception as e:
        logger.warning(f"Tavily global news failed: {e}")
        output = f"Global news unavailable: {e}"

    # --- Layer 2: SEC EDGAR Congressional Signals ---
    try:
        from tradingagents.dataflows.congressional_signals import get_congressional_trades
        congressional = get_congressional_trades(lookback_days=14, limit=10)
        output += "\n\n--- SEC EDGAR CONGRESSIONAL & INSIDER TRADE SIGNALS ---\n"
        output += congressional
        logger.info("Congressional signals appended to global news")
    except Exception as ce:
        output += f"\n[Congressional signals unavailable: {ce}]"
        logger.warning(f"Congressional signals failed: {ce}")

    # --- Layer 3: Polymarket Crowd-Probability Signals ---
    try:
        from tradingagents.dataflows.polymarket_signals import get_polymarket_signals
        poly = get_polymarket_signals(limit=5)
        output += "\n\n--- POLYMARKET CROWD-PROBABILITY SIGNALS ---\n"
        output += poly
        logger.info("Polymarket signals appended to global news")
    except Exception as pe:
        logger.warning(f"Polymarket signals failed: {pe}")

    # --- Layer 5: Geopolitical Causal Chain ---
    try:
        from tradingagents.dataflows.geopolitical_signals import get_geopolitical_signal_from_tavily
        geo_result = get_geopolitical_signal_from_tavily()
        geo_str = "Geopolitical Signal: " + str(geo_result.get("aggregate_signal", "UNKNOWN")) + " (" + str(geo_result.get("aggregate_confidence", 0)) + "%) - " + str(geo_result.get("reasoning", "No reasoning"))
        output += chr(10) + chr(10) + geo_str
        logger.info("Geopolitical layer appended to global news")
    except Exception as e:
        logger.warning(f"Geopolitical layer skipped: {e}")

    # --- Layer 6: Google Trends ---
    try:
        from tradingagents.dataflows.google_trends import get_google_trends_signal
        output += "\n\n" + get_google_trends_signal()
        logger.info("Google Trends appended to global news")
    except Exception as e:
        logger.warning(f"Google Trends skipped: {e}")

    # --- Layer 7: Whale Tracker ---
    try:
        from tradingagents.dataflows.whale_tracker import get_whale_signal
        output += "\n\n" + get_whale_signal()
        logger.info("Whale tracker appended to global news")
    except Exception as e:
        logger.warning(f"Whale tracker skipped: {e}")

    # --- Layer 8: Options Flow ---
    try:
        from tradingagents.dataflows.options_flow import get_options_flow_signal
        output += "\n\n" + get_options_flow_signal()
        logger.info("Options flow appended to global news")
    except Exception as e:
        logger.warning(f"Options flow skipped: {e}")

    # --- Layer 9: Pattern Memory ---
    try:
        from tradingagents.dataflows.pattern_memory import get_pattern_memory_context
        output += "\n\n" + get_pattern_memory_context(current_price=0.0)
        logger.info("Pattern memory appended to global news")
    except Exception as e:
        logger.warning(f"Pattern memory skipped: {e}")

    # --- Knowledge Base ---
    try:
        kb_dir = "/root/limitless-ai/knowledge_base"
        kb_text = ""
        for _kb in ["geopolitical_btc_history.md", "congressional_patterns.md", "trading_strategies.md"]:
            _kp = f"{kb_dir}/{_kb}"
            if os.path.exists(_kp):
                with open(_kp) as _kf:
                    kb_text += _kf.read()[:1500] + "\n\n"
        if kb_text:
            output += "\n\n=== KNOWLEDGE BASE ===\n" + kb_text
            logger.info("Knowledge base injected into global news context")
    except Exception as e:
        logger.warning(f"Knowledge base skipped: {e}")

    return output
