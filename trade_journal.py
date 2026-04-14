#!/usr/bin/env python3
"""
Trade Journal for Limitless AI
Logs every trading decision with full context to JSONL.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

LOGS_DIR = Path("/root/limitless-ai/logs")
JOURNAL_FILE = LOGS_DIR / "trade_journal.jsonl"

def log_decision(
    symbol: str,
    decision: str,
    confidence: int,
    price: float,
    reasoning: str,
    analyst_signals: Dict[str, Any] = None,
    mirofish_signal: Dict[str, Any] = None,
    geopolitical_signal: Dict[str, Any] = None,
    polymarket_signal: Dict[str, Any] = None,
    google_trends: Dict[str, Any] = None,
    whale_signal: Dict[str, Any] = None,
    options_flow: Dict[str, Any] = None,
    portfolio_balance: float = None,
    risk_check_result: Dict[str, Any] = None,
    kb_context_used: str = None,
) -> str:
    """
    Log a trading decision with full context.
    Returns the path to the journal file.
    """
    LOGS_DIR.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "decision": decision,
        "confidence": confidence,
        "price": price,
        "reasoning": reasoning[:1000] if reasoning else "",

        # Intelligence layer signals
        "signals": {
            "analyst_summary": analyst_signals,
            "mirofish": {
                "label": mirofish_signal.get("sentiment_label") if mirofish_signal else None,
                "score": mirofish_signal.get("sentiment_score") if mirofish_signal else None,
                "agents": mirofish_signal.get("agent_count") if mirofish_signal else None,
            } if mirofish_signal else None,
            "geopolitical": {
                "signal": geopolitical_signal.get("aggregate_signal") if geopolitical_signal else None,
                "confidence": geopolitical_signal.get("aggregate_confidence") if geopolitical_signal else None,
                "reasoning": geopolitical_signal.get("reasoning", "")[:200] if geopolitical_signal else None,
            } if geopolitical_signal else None,
            "polymarket": polymarket_signal,
            "google_trends": google_trends,
            "whale_tracker": whale_signal,
            "options_flow": options_flow,
        },

        # Portfolio state
        "portfolio": {
            "balance": portfolio_balance,
            "position_size": risk_check_result.get("position_size") if risk_check_result else None,
        },

        # Risk check
        "risk_check": {
            "approved": risk_check_result.get("approved") if risk_check_result else None,
            "checks": risk_check_result.get("checks") if risk_check_result else None,
        } if risk_check_result else None,

        # Knowledge base context
        "kb_context": kb_context_used[:500] if kb_context_used else None,
    }

    # Append to JSONL
    with open(JOURNAL_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    logger.info(f"Journal: {decision} {symbol} @ {confidence}% (${price:,.2f})")
    return str(JOURNAL_FILE)

def get_recent_entries(limit: int = 20) -> list:
    """Get the most recent journal entries."""
    if not JOURNAL_FILE.exists():
        return []

    entries = []
    with open(JOURNAL_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                continue

    return entries[-limit:]

def get_decision_stats(days: int = 30) -> Dict[str, Any]:
    """Get decision statistics for the last N days."""
    from datetime import timedelta

    entries = get_recent_entries(1000)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    recent = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            if ts >= cutoff:
                recent.append(e)
        except:
            continue

    if not recent:
        return {"total": 0, "buys": 0, "sells": 0, "holds": 0, "avg_confidence": 0, "action_rate": 0}

    buys = sum(1 for e in recent if e.get("decision") == "BUY")
    sells = sum(1 for e in recent if e.get("decision") == "SELL")
    holds = sum(1 for e in recent if e.get("decision") == "HOLD")
    avg_conf = sum(e.get("confidence", 0) for e in recent) / len(recent)

    return {
        "period_days": days,
        "total": len(recent),
        "buys": buys,
        "sells": sells,
        "holds": holds,
        "avg_confidence": round(avg_conf, 1),
        "action_rate": round((buys + sells) / len(recent) * 100, 1) if recent else 0,
    }

def get_mirofish_accuracy() -> Dict[str, Any]:
    """Calculate MiroFish signal accuracy vs actual decisions."""
    entries = get_recent_entries(1000)

    aligned = 0
    total_with_mf = 0

    for e in entries:
        mf = e.get("signals", {}).get("mirofish")
        if not mf or not mf.get("label"):
            continue

        total_with_mf += 1
        decision = e.get("decision", "HOLD")
        mf_label = mf.get("label", "").upper()

        if mf_label == "BULLISH" and decision == "BUY":
            aligned += 1
        elif mf_label == "BEARISH" and decision == "SELL":
            aligned += 1
        elif mf_label == "NEUTRAL" and decision == "HOLD":
            aligned += 1

    return {
        "total_with_mirofish": total_with_mf,
        "aligned": aligned,
        "alignment_rate": round(aligned / total_with_mf * 100, 1) if total_with_mf else 0,
    }

def print_summary():
    """Print journal summary."""
    stats = get_decision_stats(30)
    mf = get_mirofish_accuracy()
    recent = get_recent_entries(5)

    print("\n" + "="*60)
    print("LIMITLESS AI - TRADE JOURNAL SUMMARY")
    print("="*60)
    print(f"Last 30 days: {stats['total']} decisions")
    print(f"  BUY: {stats['buys']} | SELL: {stats['sells']} | HOLD: {stats['holds']}")
    print(f"  Avg Confidence: {stats['avg_confidence']}%")
    print(f"  Action Rate: {stats['action_rate']}%")
    print(f"\nMiroFish Alignment: {mf['alignment_rate']}% ({mf['aligned']}/{mf['total_with_mirofish']})")

    print("\n--- Recent Decisions ---")
    for e in recent:
        ts = e.get("timestamp", "")[:16]
        dec = e.get("decision", "?")
        conf = e.get("confidence", 0)
        price = e.get("price", 0)
        print(f"  {ts} | {dec:4} @ {conf}% | ${price:,.2f}")

    print("="*60 + "\n")

if __name__ == "__main__":
    # Demo: log a test decision
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        log_decision(
            symbol="BTC-USD",
            decision="HOLD",
            confidence=65,
            price=65000.0,
            reasoning="Test entry for journal verification",
            mirofish_signal={"sentiment_label": "BULLISH", "sentiment_score": 0.8, "agent_count": 50},
            portfolio_balance=100000.0,
        )
        print("Test entry logged.")

    print_summary()
