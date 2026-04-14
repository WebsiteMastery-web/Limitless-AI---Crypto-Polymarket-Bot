#!/usr/bin/env python3
"""
GDELT 2.0 Real-Time Tone Client
Fetches geopolitical sentiment relevant to BTC using GDELT timelinetone API.
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "LimitlessAI-GDELTClient/1.0 (trading research)"}


def get_gdelt_realtime_tone():
    """
    Query GDELT 2.0 timelinetone API for geopolitical tone across BTC-relevant topics.
    Returns dict with avg_tone, sentiment, data_points, timespan -- or None on failure.
    """
    queries = [
        "bitcoin cryptocurrency",
        "federal reserve interest rate",
        "iran ceasefire military",
        "trade war tariff sanctions",
    ]

    all_tones = []
    for query in queries:
        try:
            r = requests.get(
                GDELT_DOC_URL,
                params={
                    "query": query,
                    "mode": "timelinetone",
                    "timespan": "4H",
                    "format": "json",
                },
                timeout=10,
                headers=HEADERS,
            )
            if r.status_code == 200:
                data = r.json()
                timeline = data.get("timeline", [])
                for series in timeline:
                    if series.get("series") == "Average Tone":
                        for point in series.get("data", []):
                            val = point.get("value", 0)
                            if val != 0:  # skip zero-fill gaps
                                all_tones.append(float(val))
                logger.info(f"[GDELT] query='{query}' tone_points={len([p for s in timeline for p in s.get('data',[]) if p.get('value',0)!=0])}")
            elif r.status_code == 429:
                logger.warning(f"[GDELT] Rate limited for query='{query}', skipping")
            else:
                logger.warning(f"[GDELT] HTTP {r.status_code} for query='{query}'")
            time.sleep(2)  # Be respectful of rate limits
        except Exception as e:
            logger.warning(f"[GDELT] Failed for query='{query}': {e}")
            continue

    if not all_tones:
        logger.warning("[GDELT] No tone data collected")
        return None

    avg_tone = sum(all_tones) / len(all_tones)

    # Tone interpretation for BTC:
    # Tone > 2.0: Very positive news -> BULLISH
    # Tone < -2.0: Very negative news -> BEARISH
    # -2.0 to 2.0: Neutral
    if avg_tone > 2.0:
        sentiment = "BULLISH"
    elif avg_tone < -2.0:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    return {
        "avg_tone": round(avg_tone, 3),
        "sentiment": sentiment,
        "article_count": len(all_tones),
        "timespan": "4H",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = get_gdelt_realtime_tone()
    print(f"GDELT result: {result}")
