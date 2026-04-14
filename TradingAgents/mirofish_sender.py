"""
MiroFish Sender — runs on YOUR PC (Windows)
Runs 50-agent sentiment simulation using local Mistral 7b via Ollama.
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
NUM_AGENTS = 200

FALLBACK_HEADLINES = [
    "Bitcoin price holds above $65,000 as institutional buying continues amid macro uncertainty",
    "Federal Reserve signals no rate cuts in near term, crypto markets show mixed reaction",
    "Bitcoin whale accumulation reaches multi-month high as retail sentiment stays cautious",
    "US stock market volatility increases as trade tensions rise, Bitcoin shows resilience",
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

def run_agent(agent_id, headline):
    personality = agent_id % 5
    if personality == 0:
        role = "a risk-averse institutional trader"
    elif personality == 1:
        role = "an aggressive crypto day trader"
    elif personality == 2:
        role = "a macro economist watching Fed policy"
    elif personality == 3:
        role = "a technical analyst studying BTC charts"
    else:
        role = "a retail crypto investor"

    prompt = f"""You are {role} (Agent #{agent_id}).
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
            "options": {"num_predict": 8, "temperature": 0.7, "top_p": 0.9}
        }, timeout=30)
        response = r.json().get("response", "").strip().upper().split()[0] if r.json().get("response") else ""
        for label in ["BULLISH", "BEARISH", "NEUTRAL"]:
            if label in response:
                return label
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def run_simulation():
    print(f"\nMiroFish: Starting {NUM_AGENTS}-agent simulation with {MODEL}...")
    headline = get_latest_headline()

    results = []
    start = time.time()
    for i in range(1, NUM_AGENTS + 1):
        r = run_agent(i, headline)
        results.append(r)
        if i % 10 == 0:
            b = results.count("BULLISH")
            be = results.count("BEARISH")
            n = results.count("NEUTRAL")
            print(f"  {i}/{NUM_AGENTS} | B:{b} Be:{be} N:{n}")

    duration = round(time.time() - start, 1)
    counts = {l: results.count(l) for l in ["BULLISH", "BEARISH", "NEUTRAL"]}
    total = len(results)
    score = round((counts["BULLISH"] - counts["BEARISH"]) / total, 3)
    label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")

    print(f"\nFinal Results: {counts}")
    print(f"Score: {score} -> {label} | Duration: {duration}s")

    payload = {
        "sentiment_score": score,
        "sentiment_label": label,
        "agent_count": NUM_AGENTS,
        "model_used": MODEL,
        "duration_seconds": duration,
        "news_article": headline,
        "counts": counts,
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
        print("\nNext simulation in 2 hours. Press Ctrl+C to stop.")
        try:
            time.sleep(7200)
        except KeyboardInterrupt:
            print("Stopped.")
            break
