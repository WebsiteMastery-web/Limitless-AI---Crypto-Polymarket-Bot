"""
Limitless AI — MiroFish Bridge Server
Runs on the VPS. Receives sentiment simulation results from MiroFish
running on Sam's local PC (RTX 4060) and makes them available to
the TradingAgents pipeline as a signal layer.
"""
import os, json
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv('/root/limitless-ai/TradingAgents/.env')

MIROFISH_LOG_DIR = '/root/limitless-ai/logs/mirofish'
os.makedirs(MIROFISH_LOG_DIR, exist_ok=True)

# Latest MiroFish result — updated when PC sends a simulation result
_latest_result = None


def get_latest_mirofish_signal() -> dict:
    """
    Get the most recent MiroFish sentiment simulation result.
    Returns None if no simulation has run yet.
    """
    global _latest_result
    # Check for result files written by the PC bridge
    import glob
    files = sorted(glob.glob(f'{MIROFISH_LOG_DIR}/*.json'), reverse=True)
    if not files:
        return None
    try:
        with open(files[0]) as f:
            result = json.load(f)
        _latest_result = result
        return result
    except Exception as e:
        logger.warning(f'Failed to read MiroFish result: {e}')
        return None


def receive_mirofish_result(result: dict) -> bool:
    """
    Accept a MiroFish simulation result sent from the local PC.
    Called by the HTTP bridge endpoint.
    Expected keys: sentiment_score, sentiment_label, agent_count,
                   model_used, duration_seconds, news_article, timestamp
    """
    global _latest_result
    try:
        result['received_at'] = datetime.utcnow().isoformat()
        _latest_result = result
        timestamp = result.get('timestamp', datetime.utcnow().strftime('%Y%m%d_%H%M%S'))
        filename = f'mirofish_{timestamp}.json'
        filepath = os.path.join(MIROFISH_LOG_DIR, filename)
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f'MiroFish result received and logged: sentiment={result.get("sentiment_score")} agents={result.get("agent_count")}')
        return True
    except Exception as e:
        logger.warning(f'MiroFish result storage failed: {e}')
        return False


def format_mirofish_for_agent(result: dict) -> str:
    """Format MiroFish output as text for the TradingAgents pipeline."""
    if not result:
        return 'MiroFish sentiment simulation: No data available yet.'
    score = result.get('sentiment_score', 'N/A')
    label = result.get('sentiment_label', 'N/A')
    agents = result.get('agent_count', 'N/A')
    model = result.get('model_used', 'N/A')
    duration = result.get('duration_seconds', 'N/A')
    article = result.get('news_article', 'N/A')[:200]
    timestamp = result.get('timestamp', 'N/A')
    output = f'MiroFish Sentiment Simulation Results:\n'
    output += f'  Sentiment Score: {score} ({label})\n'
    output += f'  Simulated Agents: {agents}\n'
    output += f'  Model: {model}\n'
    output += f'  Simulation Duration: {duration}s\n'
    output += f'  Simulation Time: {timestamp}\n'
    output += f'  Source Article: {article}\n'
    output += f'  Signal Weight: Use as supplementary sentiment signal. Weight 0.15 of total decision.\n'
    return output
