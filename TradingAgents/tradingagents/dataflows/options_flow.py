"""
Options Flow Signal Layer — Limitless AI
Unusual options activity on crypto-correlated stocks (MSTR, COIN, IBIT)
is a leading indicator of institutional BTC positioning.
Uses Yahoo Finance options data (free, no auth).
"""
import requests
from datetime import datetime
from loguru import logger

CRYPTO_CORRELATED = ["MSTR", "COIN", "IBIT", "BITO"]

def get_options_flow_signal() -> str:
    """Fetch options activity for BTC-correlated stocks."""
    signals = []
    total_call_volume = 0
    total_put_volume = 0
    try:
        for ticker in CRYPTO_CORRELATED[:2]:  # Limit to 2 to stay fast
            try:
                # Use Yahoo Finance unofficial options endpoint
                url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker}"
                r = requests.get(url, timeout=8,
                    headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                data = r.json()
                result = data.get("optionChain", {}).get("result", [])
                if not result:
                    continue
                options = result[0].get("options", [])
                if not options:
                    continue
                chain = options[0]
                calls = chain.get("calls", [])
                puts = chain.get("puts", [])
                # Sum volume
                call_vol = sum(c.get("volume", 0) or 0 for c in calls)
                put_vol = sum(p.get("volume", 0) or 0 for p in puts)
                total_call_volume += call_vol
                total_put_volume += put_vol
                put_call = (put_vol / call_vol) if call_vol > 0 else 1.0
                if put_call < 0.5:
                    signal = "HEAVY CALL buying (put/call <0.5) — BULLISH BTC"
                elif put_call > 1.5:
                    signal = "HEAVY PUT buying (put/call >1.5) — BEARISH BTC"
                else:
                    signal = "BALANCED options flow — NEUTRAL"
                signals.append(
                    f"  {ticker}: calls={call_vol:,} puts={put_vol:,} "
                    f"P/C ratio={put_call:.2f} → {signal}"
                )
            except Exception:
                signals.append(f"  {ticker}: data unavailable")
        # Overall P/C ratio
        overall_pc = (total_put_volume / total_call_volume) if total_call_volume > 0 else 1.0
        if overall_pc < 0.6:
            overall = "BULLISH — institutions buying calls on crypto stocks"
        elif overall_pc > 1.4:
            overall = "BEARISH — institutions buying puts (hedging BTC exposure)"
        else:
            overall = "NEUTRAL — balanced institutional positioning"
        output = (
            "=== OPTIONS FLOW SIGNAL (Crypto-Correlated Stocks) ===\n" +
            "\n".join(signals) + "\n"
            f"Overall Put/Call ratio: {overall_pc:.2f}\n"
            f"Options flow direction: {overall}\n"
            "Note: Heavy call buying on MSTR/COIN/IBIT by institutions "
            "signals expected BTC price increase within 1-2 weeks.\n"
        )
        logger.info(f"Options flow: P/C={overall_pc:.2f}, direction={overall}")
        return output
    except Exception as e:
        logger.warning(f"Options flow failed: {e}")
        return f"Options Flow: Unavailable ({e})"
