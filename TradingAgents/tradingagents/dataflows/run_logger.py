"""
Limitless AI — Pipeline Run Logger
Every single pipeline run is logged here regardless of outcome.
Tracks MiroFish used vs not used for 90-day comparison analysis.
"""
import os, json
from datetime import datetime
from loguru import logger

RUN_LOG = '/root/limitless-ai/logs/pipeline_runs.jsonl'
os.makedirs(os.path.dirname(RUN_LOG), exist_ok=True)


def log_pipeline_run(asset: str, price: float, decision: str, confidence: int,
                     reasoning: str, mirofish_result: dict = None,
                     regime: str = None,
                     tavily_articles: int = 0, edgar_filings: int = 0,
                     polymarket_markets: int = 0,
                     raw_confidence: int = None,
                     calibrated_confidence: float = None) -> dict:
    """
    Log every pipeline run to a JSONL file for comparison analysis.
    mirofish_result=None means PC was off or MiroFish failed.
    """
    run_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    record = {
        'run_id': run_id,
        'timestamp': datetime.utcnow().isoformat(),
        'asset': asset,
        'price_at_decision': price,
        'decision': decision,
        'confidence': confidence,
        'reasoning_summary': str(reasoning)[:500],
        # MiroFish tracking
        'mirofish_used': mirofish_result is not None,
        'mirofish_sentiment': mirofish_result.get('sentiment_score') if mirofish_result else None,
        'mirofish_label': mirofish_result.get('sentiment_label') if mirofish_result else None,
        'mirofish_agents': mirofish_result.get('agent_count') if mirofish_result else None,
        # Intelligence layers active
        'tavily_articles': tavily_articles,
        'edgar_filings': edgar_filings,
        'polymarket_markets': polymarket_markets,
        # Confidence calibration
        'raw_confidence': raw_confidence if raw_confidence is not None else confidence,
        'calibrated_confidence': calibrated_confidence,
        'regime': regime or 'UNKNOWN',
    }
    with open(RUN_LOG, 'a') as f:
        f.write(json.dumps(record) + '\n')
    mf_status = f'MiroFish: {mirofish_result.get("sentiment_label", "N/A")} ({mirofish_result.get("sentiment_score", "N/A")})' if mirofish_result else 'MiroFish: NOT USED (PC off or unavailable)'
    logger.info(f'Run {run_id} logged | {decision} @ {confidence}% confidence | {mf_status}')
    return record


def get_mirofish_comparison_stats() -> str:
    """
    Generate a comparison report: runs WITH MiroFish vs WITHOUT MiroFish.
    Shows whether MiroFish-assisted decisions have better outcomes.
    """
    if not os.path.exists(RUN_LOG):
        return 'No pipeline runs logged yet.'
    with open(RUN_LOG) as f:
        runs = [json.loads(line) for line in f if line.strip()]
    if not runs:
        return 'No pipeline runs logged yet.'
    with_mf = [r for r in runs if r.get('mirofish_used')]
    without_mf = [r for r in runs if not r.get('mirofish_used')]
    def avg_confidence(rs):
        if not rs: return 0
        return sum(r.get('confidence', 0) for r in rs) / len(rs)
    def decision_counts(rs):
        counts = {}
        for r in rs:
            d = r.get('decision', 'UNKNOWN')
            counts[d] = counts.get(d, 0) + 1
        return counts
    output = f'=== LIMITLESS AI: MiroFish Comparison Report ===\n'
    output += f'Total pipeline runs: {len(runs)}\n'
    output += f'Runs WITH MiroFish:    {len(with_mf)} ({len(with_mf)/len(runs)*100:.1f}%)\n'
    output += f'Runs WITHOUT MiroFish: {len(without_mf)} ({len(without_mf)/len(runs)*100:.1f}%)\n\n'
    output += f'WITH MiroFish:\n'
    output += f'  Avg confidence: {avg_confidence(with_mf):.1f}%\n'
    output += f'  Decisions: {decision_counts(with_mf)}\n\n'
    output += f'WITHOUT MiroFish:\n'
    output += f'  Avg confidence: {avg_confidence(without_mf):.1f}%\n'
    output += f'  Decisions: {decision_counts(without_mf)}\n\n'
    output += f'Last 10 runs:\n'
    for r in runs[-10:]:
        mf = 'MF:' + str(r.get('mirofish_sentiment', '-')) if r.get('mirofish_used') else 'MF:OFF'
        output += f'  {r["timestamp"][:16]} | {r["decision"]:4} @ {r["confidence"]}% | {mf} | ${r.get("price_at_decision", 0):,.0f}\n'
    return output
