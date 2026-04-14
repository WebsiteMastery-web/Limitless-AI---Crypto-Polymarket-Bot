"""
Pattern Memory Layer — Limitless AI
Learns from past pipeline runs. Finds similar historical signal profiles
and injects what happened previously into the current decision context.
This is the system's growing intelligence — it gets smarter every run.
"""
import json
import os
from datetime import datetime, timedelta
from loguru import logger

PIPELINE_LOG = "/root/limitless-ai/logs/pipeline_runs.jsonl"
BACKTEST_LOG = "/root/limitless-ai/logs/backtest_runs.jsonl"


def _load_all_runs() -> list:
    runs = []
    for path in [PIPELINE_LOG, BACKTEST_LOG]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    try:
                        runs.append(json.loads(line.strip()))
                    except Exception:
                        pass
    return runs


def _score_similarity(run: dict, current_price: float, current_mf: str) -> float:
    score = 0.0
    # Price proximity: within 5% = high similarity
    past_price = run.get("price_at_decision", 0)
    if past_price > 0:
        price_diff = abs(current_price - past_price) / past_price
        if price_diff < 0.02: score += 3.0
        elif price_diff < 0.05: score += 2.0
        elif price_diff < 0.10: score += 1.0
    # MiroFish label match
    if current_mf and run.get("mirofish_label") == current_mf:
        score += 2.0
    return score


def get_pattern_memory_context(current_price: float, current_mf_label: str = None) -> str:
    """Find similar past situations and return what happened."""
    try:
        runs = _load_all_runs()
        if len(runs) < 3:
            return "Pattern Memory: Insufficient history (<3 runs). Building baseline."

        # Score all past runs by similarity to current conditions
        scored = []
        for r in runs:
            sim = _score_similarity(r, current_price, current_mf_label)
            if sim > 0:
                scored.append((sim, r))

        if not scored:
            return "Pattern Memory: No similar historical situations found yet."

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:3]  # Top 3 most similar

        lines = ["=== PATTERN MEMORY (Similar Past Situations) ==="]
        lines.append(f"Analyzing {len(runs)} historical runs for patterns...\n")

        for i, (sim_score, r) in enumerate(top, 1):
            ts = r.get("timestamp", "unknown")[:16]
            price = r.get("price_at_decision", 0)
            decision = r.get("decision", "UNKNOWN")
            confidence = r.get("confidence", 0)
            mf = r.get("mirofish_label", "N/A")

            # Outcome data (from backtests)
            outcome_4h = r.get("outcome_4h_pct")
            outcome_24h = r.get("outcome_24h_pct")
            was_correct = r.get("decision_correct")

            lines.append(f"Match #{i} (similarity: {sim_score:.1f}/5.0)")
            lines.append(f"  Date: {ts} | BTC: ${price:,.0f} | Decision: {decision} ({confidence}%)")
            lines.append(f"  MiroFish: {mf}")

            if outcome_4h is not None:
                lines.append(f"  Actual outcome: {outcome_4h:+.2f}% (4h) / {outcome_24h:+.2f}% (24h)")
                correct_str = "CORRECT" if was_correct else "INCORRECT"
                lines.append(f"  Decision was: {correct_str}")
            else:
                lines.append(f"  Outcome: live run, no verified result yet")

        # Summary insight
        decisions = [r.get("decision") for _, r in top]
        buy_count = decisions.count("BUY")
        sell_count = decisions.count("SELL")
        hold_count = decisions.count("HOLD")

        lines.append(f"\nHistorical pattern summary for similar conditions:")
        lines.append(f"  Past decisions: {buy_count}x BUY, {hold_count}x HOLD, {sell_count}x SELL")

        # Check if backtested runs show correctness
        correct_runs = [(s, r) for s, r in top if r.get("decision_correct") is not None]
        if correct_runs:
            correct_count = sum(1 for _, r in correct_runs if r.get("decision_correct"))
            lines.append(f"  Verified accuracy in similar situations: {correct_count}/{len(correct_runs)}")

        lines.append("\nUse this context to inform current decision — patterns repeat.")
        logger.info(f"Pattern memory: {len(runs)} total runs, {len(top)} similar situations found")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Pattern memory failed: {e}")
        return f"Pattern Memory: Unavailable ({e})"


def record_outcome(run_id: str, price_4h: float, price_24h: float) -> bool:
    """After 4h/24h, update a run record with actual outcome for learning."""
    try:
        if not os.path.exists(PIPELINE_LOG):
            return False
        with open(PIPELINE_LOG) as f:
            lines = f.readlines()
        updated = []
        for line in lines:
            r = json.loads(line)
            if r.get("run_id") == run_id:
                entry_price = r.get("price_at_decision", 0)
                decision = r.get("decision", "HOLD")
                if entry_price > 0:
                    pct_4h = (price_4h - entry_price) / entry_price * 100
                    pct_24h = (price_24h - entry_price) / entry_price * 100
                    r["outcome_4h_pct"] = round(pct_4h, 3)
                    r["outcome_24h_pct"] = round(pct_24h, 3)
                    # Was the decision correct?
                    if decision == "BUY":
                        r["decision_correct"] = pct_4h > 1.0
                    elif decision == "SELL":
                        r["decision_correct"] = pct_4h < -1.0
                    else:  # HOLD
                        r["decision_correct"] = abs(pct_4h) < 3.0
                updated.append(json.dumps(r))
            else:
                updated.append(line.strip())
        with open(PIPELINE_LOG, "w") as f:
            f.write("\n".join(updated) + "\n")
        logger.info(f"Outcome recorded for run {run_id}: 4h={price_4h}, 24h={price_24h}")
        return True
    except Exception as e:
        logger.warning(f"record_outcome failed: {e}")
        return False
