"""
Google Trends Signal Layer — Limitless AI
Retail search interest for BTC is a leading sentiment indicator.
Spikes in "bitcoin" searches often precede price moves by 24-72 hours.
Uses pytrends (free, no API key).
"""
import json
from datetime import datetime, timedelta
from loguru import logger

def get_google_trends_signal() -> str:
    """Fetch Google Trends interest for BTC-related terms."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 25))
        kw_list = ["bitcoin", "buy bitcoin", "crypto crash"]
        pytrends.build_payload(kw_list, cat=0, timeframe='now 7-d', geo='', gprop='')
        data = pytrends.interest_over_time()
        if data.empty:
            return "Google Trends: No data available."
        # Get latest values (last 24h average)
        recent = data.tail(6)  # last ~6 data points
        btc_interest = int(recent["bitcoin"].mean())
        buy_interest = int(recent["buy bitcoin"].mean())
        crash_interest = int(recent["crypto crash"].mean())
        # Interpret signal
        if btc_interest > 70:
            signal = "HIGH retail interest (>70) — potential greed/top signal"
            direction = "BEARISH (contrarian)"
        elif btc_interest < 20:
            signal = "LOW retail interest (<20) — potential fear/bottom signal"
            direction = "BULLISH (contrarian)"
        else:
            signal = "MODERATE retail interest"
            direction = "NEUTRAL"
        # 7-day trend
        week_avg = int(data["bitcoin"].mean())
        recent_avg = btc_interest
        trend = "RISING" if recent_avg > week_avg * 1.2 else ("FALLING" if recent_avg < week_avg * 0.8 else "STABLE")
        output = (
            f"=== GOOGLE TRENDS SIGNAL ===\n"
            f"Bitcoin search interest (0-100 scale):\n"
            f"  Current (24h avg): {btc_interest}/100\n"
            f"  7-day average: {week_avg}/100\n"
            f"  Trend: {trend}\n"
            f"  'Buy bitcoin' searches: {buy_interest}/100\n"
            f"  'Crypto crash' searches: {crash_interest}/100\n"
            f"Signal interpretation: {signal}\n"
            f"BTC direction implication: {direction}\n"
            f"Note: Contrarian signal — extreme retail interest = smart money sells, "
            f"extreme retail fear = smart money buys.\n"
        )
        logger.info(f"Google Trends: bitcoin={btc_interest}, trend={trend}")
        return output
    except ImportError:
        return "Google Trends: pytrends not installed. Run: pip install pytrends --break-system-packages"
    except Exception as e:
        logger.warning(f"Google Trends failed: {e}")
        return f"Google Trends: Unavailable ({e})"
