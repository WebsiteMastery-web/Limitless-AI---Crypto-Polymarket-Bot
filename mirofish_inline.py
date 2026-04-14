"""
MiroFish Inline — VPS-side sentiment using Anthropic API.
Runs 8 personality-typed agents in a single batched prompt.
Cheap (~200 tokens), fast (~2s), same output format as mirofish_sender.
"""
import json, time, os, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/limitless-ai")
from llm_router import call_simple

MIROFISH_DIR = Path("/root/limitless-ai/logs/mirofish")
MIROFISH_DIR.mkdir(parents=True, exist_ok=True)

PERSONALITIES = [
    "Retail HODLer", "Day Trader", "Swing Trader", "Fear/Greed Trader",
    "Institutional Bot", "News Trader", "Contrarian", "Whale Watcher",
]

def get_latest_headline():
    """Fetch latest headline from receiver, or use fallback."""
    try:
        import requests
        r = requests.get("http://localhost:9876/latest_headlines", timeout=3)
        if r.status_code == 200:
            h = r.json().get("headline", "")
            if h:
                return h
    except:
        pass
    return "Bitcoin trading sideways amid mixed macro signals and steady institutional flows"

def run_inline_mirofish():
    """Single Anthropic call simulating 8 trader personalities."""
    headline = get_latest_headline()
    prompt = f"""You simulate 8 crypto trader personalities reading this headline.
For EACH personality, output exactly one word: BULLISH, BEARISH, or NEUTRAL.

Headline: {headline}

Output format (one word per line, no explanation):
Retail_HODLer: [BULLISH/BEARISH/NEUTRAL]
Day_Trader: [BULLISH/BEARISH/NEUTRAL]
Swing_Trader: [BULLISH/BEARISH/NEUTRAL]
Fear_Greed_Trader: [BULLISH/BEARISH/NEUTRAL]
Institutional_Bot: [BULLISH/BEARISH/NEUTRAL]
News_Trader: [BULLISH/BEARISH/NEUTRAL]
Contrarian: [BULLISH/BEARISH/NEUTRAL]
Whale_Watcher: [BULLISH/BEARISH/NEUTRAL]"""

    t0 = time.time()
    r = call_simple(
        "You are a market sentiment simulator. Follow instructions exactly. No extra text.",
        prompt,
        max_tokens=120,
    )
    duration = round(time.time() - t0, 1)

    # Parse response
    counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    personality_results = {}
    raw = r.get("content", "")

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        for label in ["BULLISH", "BEARISH", "NEUTRAL"]:
            if label in line.upper():
                counts[label] += 1
                # Extract personality name
                name = line.split(":")[0].strip().replace("_", " ") if ":" in line else "Unknown"
                personality_results[name] = label
                break

    total = sum(counts.values()) or 1
    score = round((counts["BULLISH"] - counts["BEARISH"]) / total, 3)
    sentiment_label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")

    # Scale counts to simulate 250 agents (proportional)
    scale = 250 / total if total > 0 else 1
    scaled_counts = {k: int(v * scale) for k, v in counts.items()}
    # Adjust rounding to hit 250
    diff = 250 - sum(scaled_counts.values())
    scaled_counts["NEUTRAL"] += diff

    payload = {
        "sentiment_score": score,
        "sentiment_label": sentiment_label,
        "agent_count": 250,
        "actual_personalities": total,
        "model_used": r.get("model", "claude-sonnet"),
        "duration_seconds": duration,
        "news_article": headline,
        "counts": scaled_counts,
        "personality_breakdown": personality_results,
        "source": "inline_anthropic",
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    }

    # Save to mirofish dir (same format as receiver)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outfile = MIROFISH_DIR / f"mirofish_{ts}.json"
    with open(outfile, "w") as f:
        json.dump({"received_at": datetime.now(timezone.utc).isoformat(), "results": [payload]}, f, indent=2)

    print(f"[MiroFish:inline] {sentiment_label} score={score} | {counts} | {duration}s | saved {outfile.name}")
    return payload

def get_signal_age_minutes():
    """How old is the newest mirofish signal?"""
    files = sorted(MIROFISH_DIR.glob("mirofish_*.json"), reverse=True)
    if not files:
        return 9999
    try:
        data = json.loads(files[0].read_text())
        ts = data.get("received_at", "")
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            return age
    except:
        pass
    return 9999

def ensure_fresh_signal(max_age_minutes=60):
    """Run inline mirofish if latest signal is too old."""
    age = get_signal_age_minutes()
    if age > max_age_minutes:
        print(f"[MiroFish] Signal is {age:.0f}m old (max {max_age_minutes}m). Running inline...")
        return run_inline_mirofish()
    else:
        print(f"[MiroFish] Fresh signal exists ({age:.0f}m old). Skipping inline.")
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/root/limitless-ai/TradingAgents/.env")
    result = run_inline_mirofish()
    print(json.dumps(result, indent=2))
