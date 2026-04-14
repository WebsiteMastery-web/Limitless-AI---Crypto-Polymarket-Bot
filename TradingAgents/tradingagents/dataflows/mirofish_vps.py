"""
Limitless AI — VPS-Native MiroFish Sentiment Simulator
Runs entirely on the VPS using Ollama + phi3:mini (CPU mode).
Simulates multiple agent perspectives on a news headline and returns
a consensus sentiment score. Always available — no PC required.
"""
import os, json, requests
from datetime import datetime
from loguru import logger

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "phi3:mini"
MIROFISH_LOG_DIR = "/root/limitless-ai/logs/mirofish"
os.makedirs(MIROFISH_LOG_DIR, exist_ok=True)

AGENT_PERSONAS = [
    "You are a cautious institutional investor. Analyze this crypto news briefly.",
    "You are an aggressive crypto trader focused on momentum. Analyze this news.",
    "You are a macro economist. What does this news mean for crypto?",
    "You are a technical analyst focused on market structure. Analyze this news.",
    "You are a risk manager. What is the downside risk from this news?",
]


def _ask_agent(persona: str, news: str) -> str:
    """Ask a single agent for its sentiment on the news."""
    prompt = f"{persona}\n\nNews: {news}\n\nRespond with exactly one word: BULLISH, BEARISH, or NEUTRAL."
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 5, "temperature": 0.1}
        }, timeout=60)
        text = r.json().get("response", "").strip().upper()
        if "BULLISH" in text: return "BULLISH"
        if "BEARISH" in text: return "BEARISH"
        return "NEUTRAL"
    except Exception as e:
        logger.warning(f"Agent query failed: {e}")
        return "NEUTRAL"


def run_mirofish_simulation(news_headline: str, num_agents: int = 5) -> dict:
    """
    Run MiroFish sentiment simulation on the VPS.
    Uses phi3:mini via Ollama in CPU mode.
    Returns sentiment score and breakdown for the pipeline.
    """
    logger.info(f"MiroFish simulation starting: {num_agents} agents on VPS")
    start = datetime.utcnow()
    votes = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    for i, persona in enumerate(AGENT_PERSONAS[:num_agents], 1):
        vote = _ask_agent(persona, news_headline)
        votes[vote] += 1
        logger.info(f"  Agent {i}/{num_agents}: {vote}")
    duration = (datetime.utcnow() - start).total_seconds()
    total = sum(votes.values())
    score = (votes["BULLISH"] - votes["BEARISH"]) / total
    if score > 0.2: label = "BULLISH"
    elif score < -0.2: label = "BEARISH"
    else: label = "NEUTRAL"
    result = {
        "sentiment_score": round(score, 2),
        "sentiment_label": label,
        "agent_count": num_agents,
        "votes": votes,
        "model_used": MODEL,
        "duration_seconds": round(duration, 1),
        "news_article": news_headline[:200],
        "timestamp": start.strftime("%Y%m%d_%H%M%S"),
        "vps_native": True
    }
    filename = f'mirofish_{result["timestamp"]}.json'
    with open(f"{MIROFISH_LOG_DIR}/{filename}", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"MiroFish done: {label} ({score:.2f}) in {duration:.1f}s | votes={votes}")
    return result


def get_latest_mirofish_signal() -> dict:
    """Get most recent MiroFish result from log dir."""
    import glob
    files = sorted(glob.glob(f"{MIROFISH_LOG_DIR}/*.json"), reverse=True)
    if not files: return None
    try:
        with open(files[0]) as f: return json.load(f)
    except: return None


def format_mirofish_for_agent(result: dict) -> str:
    """Format MiroFish output for the TradingAgents pipeline."""
    if not result: return "MiroFish: No simulation data available."
    return (
        f"MiroFish VPS Sentiment Simulation:\n"
        f"  Score: {result.get('sentiment_score')} ({result.get('sentiment_label')})\n"
        f"  Votes: {result.get('votes')}\n"
        f"  Agents: {result.get('agent_count')} | Model: {result.get('model_used')}\n"
        f"  Duration: {result.get('duration_seconds')}s\n"
        f"  Article: {result.get('news_article', '')[:150]}\n"
        f"  Signal Weight: 0.15 of total decision"
    )
