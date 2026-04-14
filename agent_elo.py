#!/usr/bin/env python3
"""
Agent Elo Scoring — tracks per-layer accuracy and injects weighted context into PM.
Elo scores become statistically meaningful after 50+ resolved trades.
"""

import json
from datetime import datetime
from pathlib import Path

LAYERS = [
    "tavily_news",
    "edgar",
    "polymarket",
    "mirofish",
    "geopolitical",
    "google_trends",
    "whale_tracker",
    "options_flow",
    "pattern_memory",
]

INITIAL_ELO = 1200
ELO_PATH = Path("/root/limitless-ai/logs/agent_elo.json")


def update_elo(agent_elo, outcome_binary, k=32):
    """Update Elo after one resolved trade. outcome_binary: 1=correct, 0=wrong."""
    expected = 1 / (1 + 10 ** ((1200 - agent_elo) / 400))
    new_elo = agent_elo + k * (outcome_binary - expected)
    return round(new_elo, 1)


def get_elo_weights(elo_scores):
    """Convert Elo scores to relative weights summing to 1."""
    total = sum(elo_scores.values())
    return {layer: round(score / total, 4) for layer, score in elo_scores.items()}


def load_elo_state():
    """Load Elo state from disk or initialize with defaults."""
    try:
        with open(ELO_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "elos": {layer: INITIAL_ELO for layer in LAYERS},
            "total_updates": 0,
            "last_updated": None,
        }


def save_elo_state(state):
    ELO_PATH.parent.mkdir(exist_ok=True)
    state["last_updated"] = datetime.utcnow().isoformat()
    with open(ELO_PATH, "w") as f:
        json.dump(state, f, indent=2)


def extract_layer_alignment(trade_record, layer):
    """Return True if layer aligned with decision, False if opposed, None if unclear."""
    decision = trade_record.get("decision", "HOLD")
    if decision not in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL"):
        return None

    is_buy = decision in ("BUY", "STRONG_BUY")
    reasoning = trade_record.get("reasoning", "").lower()
    signals = trade_record.get("signals", {})

    if layer == "tavily_news":
        bull_kws = ["bullish news", "positive headline", "strong demand", "positive catalyst"]
        bear_kws = ["bearish news", "negative headline", "market fears", "selling pressure"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "edgar":
        buy_kws = ["congress bought", "senator bought", "insider bought", "institutional buying"]
        sell_kws = ["congress sold", "senator sold", "insider sold", "institutional selling"]
        buy_hits = sum(1 for kw in buy_kws if kw in reasoning)
        sell_hits = sum(1 for kw in sell_kws if kw in reasoning)
        if buy_hits > sell_hits:
            return is_buy
        elif sell_hits > buy_hits:
            return not is_buy
        return None

    elif layer == "polymarket":
        bull_kws = ["market odds favor", "prediction market bullish", "polymarket bullish"]
        bear_kws = ["prediction market bearish", "polymarket bearish", "market odds against"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "mirofish":
        # Use structured signal data directly — most reliable
        mf = signals.get("mirofish", {})
        if not mf or mf.get("label") is None:
            return None
        label = mf.get("label", "NEUTRAL")
        if label == "BULLISH":
            return is_buy
        elif label == "BEARISH":
            return not is_buy
        return None

    elif layer == "geopolitical":
        bull_kws = ["geopolitical bullish", "geopolitical tailwind", "risk-on", "positive geopolitical"]
        bear_kws = ["geopolitical bearish", "geopolitical headwind", "risk-off", "geopolitical tension"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "google_trends":
        bull_kws = ["contrarian bullish", "search interest low", "fomo low"]
        bear_kws = ["contrarian bearish", "search interest high", "peak fomo"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "whale_tracker":
        bull_kws = ["whale buying", "large wallet accumulation", "whale accumulation"]
        bear_kws = ["whale selling", "large wallet distribution", "whale distribution"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "options_flow":
        bull_kws = ["bullish options", "call buying", "options bullish", "unusual call"]
        bear_kws = ["bearish options", "put buying", "options bearish", "unusual put"]
        bull_hits = sum(1 for kw in bull_kws if kw in reasoning)
        bear_hits = sum(1 for kw in bear_kws if kw in reasoning)
        if bull_hits > bear_hits:
            return is_buy
        elif bear_hits > bull_hits:
            return not is_buy
        return None

    elif layer == "pattern_memory":
        if any(kw in reasoning for kw in ["similar situation", "pattern match", "historically", "past pattern"]):
            return True
        return None

    return None


def update_elos_from_resolved_trade(trade_record, outcome):
    """Update Elo scores after a trade resolves. outcome: 'WIN' or 'LOSS'."""
    state = load_elo_state()
    outcome_binary = 1 if outcome == "WIN" else 0
    updated = []

    for layer in LAYERS:
        layer_aligned = extract_layer_alignment(trade_record, layer)
        if layer_aligned is not None:
            layer_outcome = outcome_binary if layer_aligned else (1 - outcome_binary)
            old_elo = state["elos"][layer]
            state["elos"][layer] = update_elo(old_elo, layer_outcome)
            updated.append(f"{layer}: {old_elo:.1f} -> {state['elos'][layer]:.1f}")

    state["total_updates"] += 1
    save_elo_state(state)
    return state, updated


def update_elos_from_recent(lookback_hours=8):
    """Resolve recent trades using next-price comparison. Called by weekly cron."""
    from datetime import timedelta

    journal_path = Path("/root/limitless-ai/logs/trade_journal.jsonl")
    if not journal_path.exists():
        print("No trade journal found")
        return

    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    trades = []
    with open(journal_path) as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                ts = datetime.fromisoformat(t["timestamp"].replace("Z", ""))
                if ts >= cutoff:
                    trades.append((ts, t))
            except Exception:
                continue

    trades.sort(key=lambda x: x[0])
    resolved = 0

    for i, (ts, trade) in enumerate(trades[:-1]):
        decision = trade.get("decision", "HOLD")
        if decision not in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL"):
            continue

        entry_price = trade.get("price", 0)
        if entry_price <= 0:
            continue

        next_price = trades[i + 1][1].get("price", 0)
        if next_price <= 0:
            continue

        price_change = (next_price - entry_price) / entry_price
        is_buy = decision in ("BUY", "STRONG_BUY")
        outcome = "WIN" if (is_buy and price_change > 0) or (not is_buy and price_change < 0) else "LOSS"

        _, updates = update_elos_from_resolved_trade(trade, outcome)
        resolved += 1
        print(f"[{ts.strftime('%H:%M')}] {decision} @ {entry_price:.0f} -> {next_price:.0f} ({outcome}) {price_change*100:.2f}%")
        for u in updates:
            print(f"  {u}")

    print(f"\nResolved {resolved} trades")
    state = load_elo_state()
    weights = get_elo_weights(state["elos"])
    print(f"Total Elo updates: {state['total_updates']}")
    for layer, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {layer}: Elo {state['elos'][layer]:.0f}, weight {weight:.3f}")


if __name__ == "__main__":
    state = load_elo_state()
    weights = get_elo_weights(state["elos"])
    print("Elo state initialized:")
    for layer, elo in state["elos"].items():
        print(f"  {layer}: {elo}")
    print(f"Weights: {weights}")
    save_elo_state(state)
    print(f"Saved to {ELO_PATH}")
