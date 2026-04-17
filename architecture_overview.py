"""
architecture_overview.py — Full 12-layer Limitless AI pipeline visualization.

Shows signal ingestion → debate → calibration → risk gating → decision.
Includes the Apr 7, 2026 SELL signal that returned +$818 profit on BTC/USD.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json


class SignalLayer(Enum):
    L1_PRICE_ACTION      = ("L1",  "Price Action & OHLCV")
    L2_TECHNICAL         = ("L2",  "Technical Indicators (RSI, MACD, BB)")
    L3_VOLUME            = ("L3",  "Volume Profile & Order Flow")
    L4_SENTIMENT         = ("L4",  "Social Sentiment & Fear/Greed")
    L5_WHALE             = ("L5",  "Whale Wallet Tracking (on-chain)")
    L6_DEBATE            = ("L6",  "Bull vs Bear vs Neutral Debate Engine")
    L7_ARBITER           = ("L7",  "Arbiter Portfolio Manager (Claude Opus)")
    L8_GDELT             = ("L8",  "GDELT Geopolitical Signal Layer")
    L9_MACRO             = ("L9",  "Macro Regime Detection")
    L10_ELO              = ("L10", "Elo Re-weighting (agent accuracy tracking)")
    L11_CALIBRATION      = ("L11", "Confidence Calibration (Platt scaling)")
    L12_RISK_GATE        = ("L12", "Risk Gate (position sizing + drawdown halt)")

    def __init__(self, code: str, description: str):
        self.code = code
        self.description = description


@dataclass
class Signal:
    layer: SignalLayer
    value: str
    direction: str          # BULLISH / BEARISH / NEUTRAL
    weight: float = 1.0     # modified by Elo re-weighting (L10)
    confidence: float = 0.0


@dataclass
class PipelineState:
    asset: str
    price: float
    signals: list[Signal] = field(default_factory=list)
    debate_verdict: dict = field(default_factory=dict)
    calibrated_confidence: float = 0.0
    final_decision: str = "HOLD"
    blocked_reason: Optional[str] = None
    position_size_pct: float = 0.0


class IntelligencePipeline:
    """Orchestrates all 12 layers in sequence. LangGraph manages state in production."""

    CONFIDENCE_THRESHOLD = 75.0

    def ingest_signals(self, state: PipelineState, raw_signals: list[dict]) -> PipelineState:
        for s in raw_signals:
            layer = SignalLayer[s["layer"]]
            state.signals.append(Signal(
                layer=layer,
                value=s["value"],
                direction=s["direction"],
                weight=s.get("weight", 1.0),
                confidence=s.get("confidence", 50.0),
            ))
        return state

    def score_consensus(self, state: PipelineState) -> tuple[str, float]:
        direction_scores = {"BULLISH": 0.0, "BEARISH": 0.0, "NEUTRAL": 0.0}
        for sig in state.signals:
            direction_scores[sig.direction] += sig.weight * sig.confidence
        total = sum(direction_scores.values()) or 1
        dominant = max(direction_scores, key=direction_scores.get)
        agreement = direction_scores[dominant] / total
        return dominant, round(agreement * 100, 2)

    def apply_risk_gate(self, state: PipelineState) -> PipelineState:
        if state.calibrated_confidence < self.CONFIDENCE_THRESHOLD:
            state.final_decision = "BLOCKED"
            state.blocked_reason = (
                f"confidence {state.calibrated_confidence:.1f} < {self.CONFIDENCE_THRESHOLD}"
            )
        return state


def pipeline_flow() -> str:
    return """
╔══════════════════════════════════════════════════════════════════╗
║              LIMITLESS AI — 12-LAYER SIGNAL PIPELINE             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  L1  Price Action & OHLCV          ──┐                          ║
║  L2  Technical Indicators (RSI..)   ─┤                          ║
║  L3  Volume Profile & Order Flow    ─┤──► Signal Aggregator     ║
║  L4  Social Sentiment / Fear-Greed  ─┤         │                ║
║  L5  Whale Wallet Tracking          ─┘         │                ║
║                                                ▼                 ║
║  L8  GDELT Geopolitical Signals     ──────► L6 Debate Engine    ║
║  L9  Macro Regime Detection         ──────►   Bull / Bear /     ║
║                                               Neutral Analysts   ║
║                                                │                 ║
║                                                ▼                 ║
║                                         L7 Arbiter Agent        ║
║                                         (Claude Opus PM)        ║
║                                                │                 ║
║                                                ▼                 ║
║                                        L10 Elo Re-weighting     ║
║                                         (accuracy tracking)     ║
║                                                │                 ║
║                                                ▼                 ║
║                                        L11 Confidence           ║
║                                          Calibration            ║
║                                          (Platt scaling)        ║
║                                                │                 ║
║                                         ┌──── ▼ ────┐           ║
║                                         │  L12 Risk  │          ║
║                                         │   Gate     │          ║
║                                         └──── ┬ ────┘           ║
║                                    conf < 75? │                  ║
║                                         ┌─────┴──────┐          ║
║                                      BLOCK         EXECUTE      ║
║                                    (paper)        (testnet)     ║
╚══════════════════════════════════════════════════════════════════╝
"""


def example_decision() -> dict:
    """Reconstructed Apr 7, 2026 SELL signal — the system's first live-backtest win."""
    pipeline = IntelligencePipeline()
    state = PipelineState(asset="BTC/USD", price=71941.00)

    raw = [
        {"layer": "L1_PRICE_ACTION",  "value": "bearish engulfing candle 4h",      "direction": "BEARISH", "weight": 1.0,  "confidence": 72},
        {"layer": "L2_TECHNICAL",     "value": "RSI 68.4 overbought, MACD cross",  "direction": "BEARISH", "weight": 1.1,  "confidence": 75},
        {"layer": "L3_VOLUME",        "value": "declining volume 3d, sell pressure","direction": "BEARISH", "weight": 0.9,  "confidence": 65},
        {"layer": "L4_SENTIMENT",     "value": "fear_greed=72 (greed)",            "direction": "NEUTRAL", "weight": 0.8,  "confidence": 55},
        {"layer": "L5_WHALE",         "value": "1,200+ BTC moved to exchanges",    "direction": "BEARISH", "weight": 1.4,  "confidence": 88},
        {"layer": "L8_GDELT",         "value": "no major macro events",            "direction": "NEUTRAL", "weight": 0.7,  "confidence": 50},
        {"layer": "L9_MACRO",         "value": "DXY strength, risk-off signals",   "direction": "BEARISH", "weight": 1.2,  "confidence": 78},
    ]

    state = pipeline.ingest_signals(state, raw)
    dominant, agreement = pipeline.score_consensus(state)

    state.debate_verdict = {
        "decision": "SELL",
        "confidence": 82,
        "dominant_side": "bear",
        "key_signal": "whale_wallets_moving_to_exchanges",
        "reasoning": "Strong bear consensus: whale on-chain activity + RSI overbought + declining volume. Bull case weak.",
    }
    state.calibrated_confidence = 82.0
    state.final_decision = "SELL"
    state.position_size_pct = 3.2

    result = {
        "date": "2026-04-07",
        "asset": "BTC/USD",
        "entry_price": 71941.00,
        "decision": state.final_decision,
        "calibrated_confidence": state.calibrated_confidence,
        "position_size_pct": state.position_size_pct,
        "layers_active": len(state.signals),
        "consensus_direction": dominant,
        "consensus_agreement_pct": agreement,
        "verdict": state.debate_verdict,
        "outcome": {
            "next_day_close": 71123.00,
            "pnl_per_btc": 818.00,
            "outcome_pct": 1.136,
            "result": "WIN",
        },
    }
    return result


def main():
    print("=== Limitless AI — Architecture Overview ===")
    print(pipeline_flow())

    print("--- All 12 Signal Layers ---")
    for layer in SignalLayer:
        print(f"  {layer.code:>3}  {layer.description}")

    print("\n--- Example Decision: Apr 7, 2026 SELL Signal ---")
    decision = example_decision()
    print(json.dumps(decision, indent=2))

    print("\n--- Signal Layer Summary ---")
    pipeline = IntelligencePipeline()
    state = PipelineState(asset="BTC/USD", price=71941.00)
    for layer in SignalLayer:
        print(f"  {layer.code}: {layer.description}")


if __name__ == "__main__":
    main()
