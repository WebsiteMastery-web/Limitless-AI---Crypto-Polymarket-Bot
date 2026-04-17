"""
risk_manager_sample.py — L11 Confidence Calibration + L12 Risk Gating in Limitless AI.

The system never executes a trade unless calibrated confidence exceeds 75%.
This demonstrates the structural safety layer — not a feature, the architecture itself.
Paper trading only (Binance testnet + Polymarket paper positions).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import math


CONFIDENCE_THRESHOLD = 75       # minimum to open any position
MAX_POSITION_PCT = 0.05         # max 5% of portfolio per trade
KELLY_FRACTION = 0.25           # fractional Kelly to limit ruin risk


class TradeDecision(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


@dataclass
class ConfidenceScore:
    raw: float                  # raw model output 0-100
    calibrated: float           # after historical accuracy adjustment
    sample_size: int            # number of historical signals used
    win_rate: float             # historical win rate for this signal pattern
    signal_agreement: float     # fraction of layers that agreed (0-1)

    @property
    def is_tradeable(self) -> bool:
        return self.calibrated >= CONFIDENCE_THRESHOLD and self.sample_size >= 10


@dataclass
class RiskProfile:
    portfolio_value: float
    max_drawdown_pct: float = 0.15   # halt if drawdown exceeds 15%
    current_drawdown_pct: float = 0.0
    open_positions: int = 0
    max_concurrent: int = 3


class ConfidenceCalibrator:
    """
    Adjusts raw model confidence using Platt scaling against historical accuracy.
    Elo re-weighting (L10) feeds win_rate per agent; this layer integrates it.
    """

    def __init__(self, historical_accuracy: float = 0.55):
        self.base_accuracy = historical_accuracy

    def calibrate(self, raw: float, win_rate: float, sample_size: int, signal_agreement: float) -> ConfidenceScore:
        if sample_size < 10:
            # Shrink toward 50 when we don't have enough history
            shrinkage = sample_size / 10
            calibrated = 50 + (raw - 50) * shrinkage * 0.5
        else:
            # Scale by win rate relative to baseline
            accuracy_ratio = win_rate / self.base_accuracy
            calibrated = raw * min(accuracy_ratio, 1.2)

        # Agreement discount: if only 60% of layers agreed, penalize
        agreement_factor = 0.5 + 0.5 * signal_agreement
        calibrated = calibrated * agreement_factor

        return ConfidenceScore(
            raw=raw,
            calibrated=round(calibrated, 2),
            sample_size=sample_size,
            win_rate=win_rate,
            signal_agreement=signal_agreement,
        )


class RiskGate:
    """
    L12: Final gate before any trade execution.
    Blocks trades, computes Kelly position size, enforces drawdown halts.
    """

    def __init__(self, profile: RiskProfile):
        self.profile = profile

    def should_trade(self, score: ConfidenceScore, decision: TradeDecision) -> tuple[bool, str]:
        if decision == TradeDecision.HOLD:
            return False, "decision_is_hold"

        if self.profile.current_drawdown_pct >= self.profile.max_drawdown_pct:
            return False, f"drawdown_halt ({self.profile.current_drawdown_pct:.1%} >= {self.profile.max_drawdown_pct:.1%})"

        if self.profile.open_positions >= self.profile.max_concurrent:
            return False, f"max_positions_reached ({self.profile.open_positions})"

        if not score.is_tradeable:
            reason = (
                f"confidence_below_threshold ({score.calibrated:.1f} < {CONFIDENCE_THRESHOLD})"
                if score.calibrated < CONFIDENCE_THRESHOLD
                else f"insufficient_sample_size ({score.sample_size} < 10)"
            )
            return False, reason

        return True, "approved"

    def position_size(self, score: ConfidenceScore, asset_price: float) -> dict:
        """Fractional Kelly sizing, capped at MAX_POSITION_PCT of portfolio."""
        p = score.win_rate
        q = 1 - p
        # Assume 1:1 win/loss ratio for conservative sizing
        kelly_full = (p - q)
        kelly_fractional = max(kelly_full * KELLY_FRACTION, 0)
        pct = min(kelly_fractional, MAX_POSITION_PCT)
        usd_size = self.profile.portfolio_value * pct
        units = usd_size / asset_price if asset_price > 0 else 0
        return {
            "pct_of_portfolio": round(pct * 100, 2),
            "usd_size": round(usd_size, 2),
            "units": round(units, 6),
            "kelly_full": round(kelly_full * 100, 2),
            "kelly_fractional": round(kelly_fractional * 100, 2),
        }


def run_risk_gate_sample():
    """Test risk gate across low, borderline, and high confidence scenarios."""
    calibrator = ConfidenceCalibrator(historical_accuracy=0.55)
    profile = RiskProfile(portfolio_value=10_000, current_drawdown_pct=0.03, open_positions=1)
    gate = RiskGate(profile)

    scenarios = [
        # (label, raw, win_rate, sample_size, signal_agreement, decision)
        ("Apr 7 SELL signal — strong bear consensus", 82, 0.67, 24, 0.83, TradeDecision.SELL),
        ("Borderline signal — mixed layers",          68, 0.54, 15, 0.60, TradeDecision.BUY),
        ("Weak signal — insufficient history",        79, 0.58,  6, 0.70, TradeDecision.BUY),
        ("Below threshold — confidence gate blocks",  60, 0.50, 20, 0.50, TradeDecision.BUY),
        ("HOLD signal — gate irrelevant",             85, 0.70, 30, 0.90, TradeDecision.HOLD),
    ]

    print("=== Limitless AI — Risk Gate + Confidence Calibration Sample ===\n")
    print(f"Portfolio: ${profile.portfolio_value:,} | Drawdown: {profile.current_drawdown_pct:.1%} | "
          f"Open positions: {profile.open_positions}/{profile.max_concurrent}\n")

    for label, raw, win_rate, n, agreement, decision in scenarios:
        score = calibrator.calibrate(raw, win_rate, n, agreement)
        tradeable, reason = gate.should_trade(score, decision)
        print(f"--- {label}")
        print(f"    Raw: {raw} | Calibrated: {score.calibrated} | Tradeable: {score.is_tradeable}")
        print(f"    Decision: {decision.value} | Gate: {'APPROVED' if tradeable else 'BLOCKED'} ({reason})")
        if tradeable:
            sizing = gate.position_size(score, asset_price=71941.0)
            print(f"    Position: {sizing['pct_of_portfolio']}% of portfolio = ${sizing['usd_size']:,} ({sizing['units']} BTC)")
        print()


if __name__ == "__main__":
    run_risk_gate_sample()
