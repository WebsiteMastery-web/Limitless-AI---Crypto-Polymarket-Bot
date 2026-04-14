"""
MiroFish Sender — runs on YOUR PC (Windows)
Runs 250-agent sentiment simulation using local Mistral 7b via Ollama.
Sends result to VPS automatically. Run before pipeline for best signal.
Leave running (loops every 2 hours) or run once manually.

Usage: python C:\mirofish_sender.py
"""
import requests
import json
import time
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
VPS_URL = "http://167.71.25.250:9876/mirofish"
VPS_NEWS_URL = "http://167.71.25.250:9876/latest_headlines"
MODEL = "mistral:7b"
NUM_AGENTS = 250

FALLBACK_HEADLINES = [
    "Bitcoin price holds above $65,000 as institutional buying continues amid macro uncertainty",
    "Federal Reserve signals no rate cuts in near term, crypto markets show mixed reaction",
    "Bitcoin whale accumulation reaches multi-month high as retail sentiment stays cautious",
    "US stock market volatility increases as trade tensions rise, Bitcoin shows resilience",
]

# 8 distinct trader personality types
PERSONALITY_TYPES = [
    {
        "type": "Retail HODLer",
        "role": "a long-term conviction Bitcoin holder who believes in crypto fundamentals",
        "style": "You buy dips and hold for years. You are not swayed by short-term noise."
    },
    {
        "type": "Day Trader",
        "role": "a momentum-focused crypto day trader who reads technical signals",
        "style": "You trade intraday, follow RSI, MACD, and volume spikes for entry/exit."
    },
    {
        "type": "Swing Trader",
        "role": "a swing trader with a 1-2 week horizon who is macro-aware",
        "style": "You look at weekly charts, macro catalysts, and earnings for positioning."
    },
    {
        "type": "Fear/Greed Trader",
        "role": "an emotional, crowd-following retail investor driven by fear and greed",
        "style": "You FOMO buy when everyone is bullish and panic sell when scared."
    },
    {
        "type": "Institutional Bot",
        "role": "a systematic institutional trading algorithm with risk-adjusted sizing",
        "style": "You follow quantitative signals, manage drawdowns, and size positions precisely."
    },
    {
        "type": "News Trader",
        "role": "a news-driven trader who reacts purely to headlines and announcements",
        "style": "You trade the immediate market reaction to news, not the fundamentals."
    },
    {
        "type": "Contrarian",
        "role": "a contrarian investor who always fades consensus and crowd sentiment",
        "style": "When everyone is bullish you get bearish; when fearful you buy aggressively."
    },
    {
        "type": "Whale Watcher",
        "role": "an on-chain analyst who follows large wallet movements and exchange flows",
        "style": "You track whale accumulation, exchange outflows, and large OTC deals."
    },
]

def get_latest_headline():
    try:
        r = requests.get(VPS_NEWS_URL, timeout=5)
        if r.status_code == 200:
            data = r.json()
            headline = data.get("headline", "")
            if headline:
                print(f"Live headline from VPS: {headline[:80]}")
                return headline
    except:
        pass
    headline = FALLBACK_HEADLINES[datetime.now().hour % len(FALLBACK_HEADLINES)]
    print(f"Using fallback headline: {headline[:80]}")
    return headline

def get_personality(agent_id):
    """Distribute 250 agents across 8 personality types (~31-32 each)."""
    return PERSONALITY_TYPES[agent_id % len(PERSONALITY_TYPES)]

def run_agent(agent_id, headline):
    personality = get_personality(agent_id)
    role = personality["role"]
    style = personality["style"]
    ptype = personality["type"]

    prompt = f"""You are {role} (Agent #{agent_id}, type: {ptype}).
{style}

Read this crypto/market headline carefully and give your market sentiment.
Respond with EXACTLY one word: BULLISH, BEARISH, or NEUTRAL.
Do not explain. Do not add punctuation. Just the single word.

Headline: {headline}

Your sentiment (one word only):"""

    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 8, "temperature": 0.75, "top_p": 0.9}
        }, timeout=30)
        response = r.json().get("response", "").strip().upper().split()[0] if r.json().get("response") else ""
        for label in ["BULLISH", "BEARISH", "NEUTRAL"]:
            if label in response:
                return label, ptype
        return "NEUTRAL", ptype
    except:
        return "NEUTRAL", ptype

def run_simulation():
    print(f"
MiroFish: Starting {NUM_AGENTS}-agent simulation with {MODEL}...")
    print(f"Using 8 personality types: {[p['type'] for p in PERSONALITY_TYPES]}")
    headline = get_latest_headline()

    results = []
    personality_results = {p["type"]: {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0} for p in PERSONALITY_TYPES}
    start = time.time()

    for i in range(1, NUM_AGENTS + 1):
        r, ptype = run_agent(i, headline)
        results.append(r)
        personality_results[ptype][r] += 1
        if i % 25 == 0:
            b = results.count("BULLISH")
            be = results.count("BEARISH")
            n = results.count("NEUTRAL")
            print(f"  {i}/{NUM_AGENTS} | B:{b} Be:{be} N:{n}")

    duration = round(time.time() - start, 1)
    counts = {l: results.count(l) for l in ["BULLISH", "BEARISH", "NEUTRAL"]}
    total = len(results)
    score = round((counts["BULLISH"] - counts["BEARISH"]) / total, 3)
    label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")

    print(f"
Final Results: {counts}")
    print(f"Score: {score} -> {label} | Duration: {duration}s")
    print(f"By personality: {personality_results}")

    payload = {
        "sentiment_score": score,
        "sentiment_label": label,
        "agent_count": NUM_AGENTS,
        "model_used": MODEL,
        "duration_seconds": duration,
        "news_article": headline,
        "counts": counts,
        "personality_breakdown": personality_results,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }

    try:
        r = requests.post(VPS_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"Sent to VPS: OK")
        else:
            print(f"VPS returned: {r.status_code}")
    except Exception as e:
        print(f"VPS unreachable: {e}")
        with open("mirofish_latest.json", "w") as f:
            json.dump(payload, f)
        print("Saved locally as fallback.")

    return payload

if __name__ == "__main__":
    while True:
        run_simulation()
        print("
Next simulation in 2 hours. Press Ctrl+C to stop.")
        try:
            time.sleep(7200)
        except KeyboardInterrupt:
            print("Stopped.")
            break
