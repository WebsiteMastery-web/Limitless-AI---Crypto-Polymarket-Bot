"""
debate_engine_sample.py — Multi-agent debate layer (L6) of Limitless AI.

Demonstrates how Bull, Bear, and Neutral analysts independently analyze
market signals, then an Arbiter synthesizes their arguments into a verdict.
Full system uses LangGraph orchestration; this sample shows the core logic.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional
import anthropic

CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = "claude-opus-4-6"

SYSTEM_TEMPLATES = {
    "bull": (
        "You are a professional BULL analyst. Your job is to construct the strongest "
        "possible bullish case for the given asset using the provided signals. "
        "Be specific, cite the signals, and give a confidence score 0-100."
    ),
    "bear": (
        "You are a professional BEAR analyst. Your job is to construct the strongest "
        "possible bearish case for the given asset using the provided signals. "
        "Be specific, cite the signals, and give a confidence score 0-100."
    ),
    "neutral": (
        "You are a NEUTRAL market analyst. Identify which signals conflict, which "
        "are ambiguous, and what additional data would resolve the uncertainty. "
        "Give a confidence score 0-100 for your uncertainty assessment."
    ),
    "arbiter": (
        "You are an Arbiter Portfolio Manager synthesizing a Bull, Bear, and Neutral "
        "debate. Weigh each argument. Output JSON with keys: "
        "decision (BUY/SELL/HOLD), confidence (0-100), reasoning (str), "
        "dominant_side (bull/bear/neutral), key_signal (str)."
    ),
}


@dataclass
class MarketContext:
    asset: str
    price: float
    signals: dict
    timeframe: str = "24h"


@dataclass
class DebatePosition:
    side: str
    argument: str
    confidence: int
    raw_response: str = ""


@dataclass
class DebateResult:
    bull: DebatePosition
    bear: DebatePosition
    neutral: DebatePosition
    verdict: dict = field(default_factory=dict)


class DebateAgent:
    def __init__(self, side: str):
        self.side = side
        self.system = SYSTEM_TEMPLATES[side]

    def argue(self, context: MarketContext) -> DebatePosition:
        prompt = (
            f"Asset: {context.asset} @ ${context.price:,.2f}\n"
            f"Timeframe: {context.timeframe}\n\n"
            f"Signals:\n{json.dumps(context.signals, indent=2)}\n\n"
            f"Build your {self.side.upper()} case. Include confidence score."
        )
        resp = CLIENT.messages.create(
            model=MODEL,
            max_tokens=600,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        # Parse confidence from response (last integer found)
        import re
        scores = re.findall(r'\b(\d{1,3})\b', text)
        confidence = int(scores[-1]) if scores else 50
        confidence = min(max(confidence, 0), 100)
        return DebatePosition(side=self.side, argument=text, confidence=confidence, raw_response=text)


class ArbiterAgent:
    def __init__(self):
        self.system = SYSTEM_TEMPLATES["arbiter"]

    def judge(self, context: MarketContext, result: DebateResult) -> dict:
        prompt = (
            f"Asset: {context.asset} @ ${context.price:,.2f}\n\n"
            f"BULL CASE (confidence {result.bull.confidence}):\n{result.bull.argument}\n\n"
            f"BEAR CASE (confidence {result.bear.confidence}):\n{result.bear.argument}\n\n"
            f"NEUTRAL ASSESSMENT (confidence {result.neutral.confidence}):\n{result.neutral.argument}\n\n"
            "Synthesize all three positions. Output valid JSON only."
        )
        resp = CLIENT.messages.create(
            model=MODEL,
            max_tokens=400,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"decision": "HOLD", "confidence": 50, "reasoning": text, "dominant_side": "neutral", "key_signal": "parse_error"}


def run_debate_sample():
    """Run a full debate cycle using the Apr 7 2026 backtest context."""
    ctx = MarketContext(
        asset="BTC/USD",
        price=71941.00,
        signals={
            "whale_activity": "BEARISH — 3 wallets moved 1,200+ BTC to exchanges in 6h",
            "rsi_14": 68.4,
            "macd": "bearish_crossover",
            "gdelt_geopolitical": "NEUTRAL — no significant macro events",
            "fear_greed_index": 72,
            "order_book_imbalance": -0.18,
            "funding_rate": 0.021,
            "volume_trend": "declining_3d",
        },
        timeframe="24h",
    )

    bull = DebateAgent("bull")
    bear = DebateAgent("bear")
    neutral = DebateAgent("neutral")
    arbiter = ArbiterAgent()

    print(f"=== Limitless AI — Debate Engine Sample ===")
    print(f"Asset: {ctx.asset} @ ${ctx.price:,.2f}\n")

    print("[L6] Running Bull analyst...")
    bull_pos = bull.argue(ctx)
    print(f"Bull confidence: {bull_pos.confidence}\n")

    print("[L6] Running Bear analyst...")
    bear_pos = bear.argue(ctx)
    print(f"Bear confidence: {bear_pos.confidence}\n")

    print("[L6] Running Neutral analyst...")
    neutral_pos = neutral.argue(ctx)
    print(f"Neutral confidence: {neutral_pos.confidence}\n")

    result = DebateResult(bull=bull_pos, bear=bear_pos, neutral=neutral_pos)

    print("[L7] Arbiter synthesizing debate...")
    verdict = arbiter.judge(ctx, result)
    result.verdict = verdict

    print("\n=== VERDICT ===")
    print(json.dumps(verdict, indent=2))
    print(f"\nHistorical result: SELL @ $71,941 → closed $71,123 (+$818 profit)")
    return result


if __name__ == "__main__":
    run_debate_sample()
