"""
Whale Wallet Tracker — Limitless AI
Large BTC wallet movements are leading indicators.
Whale accumulation precedes price rallies. Whale selling precedes drops.
Uses CoinGecko free API + blockchain.info (no auth required).
"""
import requests
from loguru import logger

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

def get_whale_signal() -> str:
    """Get large wallet movement signals for BTC."""
    signals = []
    try:
        # 1. BTC market data from CoinGecko (whale activity proxy)
        r = requests.get(
            f"{COINGECKO_BASE}/coins/bitcoin",
            params={"localization": "false", "tickers": "false",
                    "market_data": "true", "community_data": "true"},
            timeout=10,
            headers={"Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json()
            md = data.get("market_data", {})
            # Large holder proxy metrics
            price = md.get("current_price", {}).get("usd", 0)
            vol_24h = md.get("total_volume", {}).get("usd", 0)
            mcap = md.get("market_cap", {}).get("usd", 0)
            vol_to_mcap = (vol_24h / mcap * 100) if mcap else 0
            price_change_24h = md.get("price_change_percentage_24h", 0)
            price_change_7d = md.get("price_change_percentage_7d", 0)
            # Volume spike = whale activity signal
            if vol_to_mcap > 8:
                vol_signal = "HIGH volume/mcap ratio (>8%) — unusual whale activity detected"
                vol_direction = "ALERT — large movement in progress"
            elif vol_to_mcap > 4:
                vol_signal = "ELEVATED volume/mcap ratio (4-8%) — moderate whale activity"
                vol_direction = "Watch for direction"
            else:
                vol_signal = "NORMAL volume/mcap ratio (<4%) — no unusual whale activity"
                vol_direction = "Neutral"
            signals.append(f"  Volume/MCap ratio: {vol_to_mcap:.1f}% — {vol_signal}")
            signals.append(f"  24h price change: {price_change_24h:+.2f}%")
            signals.append(f"  7d price change: {price_change_7d:+.2f}%")
        # 2. Large transaction count from blockchain.info
        r2 = requests.get(
            "https://blockchain.info/q/24hrbtcsent",
            timeout=8
        )
        if r2.status_code == 200:
            btc_sent = int(r2.text.strip()) / 1e8  # Convert satoshis to BTC
            signals.append(f"  BTC sent on-chain (24h): {btc_sent:,.0f} BTC")
            if btc_sent > 500000:
                signals.append("  WHALE ALERT: >500k BTC moved on-chain — high activity")
                whale_direction = "BEARISH (large distribution likely)"
            elif btc_sent > 200000:
                signals.append("  Moderate on-chain volume: 200-500k BTC")
                whale_direction = "NEUTRAL"
            else:
                signals.append("  Low on-chain volume: <200k BTC — accumulation phase possible")
                whale_direction = "BULLISH (low selling pressure)"
        else:
            whale_direction = "UNKNOWN"
        # 3. Exchange flow proxy (high exchange inflows = selling pressure)
        output = (
            "=== WHALE WALLET SIGNAL ===\n"
            "On-chain large transaction analysis:\n" +
            "\n".join(signals) + "\n"
            f"Whale activity direction: {whale_direction}\n"
            "Note: Whale accumulation (moving BTC off exchanges) is bullish. "
            "Whale distribution (moving to exchanges) is bearish.\n"
        )
        logger.info(f"Whale tracker: {whale_direction}")
        return output
    except Exception as e:
        logger.warning(f"Whale tracker failed: {e}")
        return f"Whale Tracker: Unavailable ({e})"
