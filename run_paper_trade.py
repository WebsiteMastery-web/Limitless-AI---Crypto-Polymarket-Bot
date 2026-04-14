#!/usr/bin/env python3
"""
Limitless AI — Main Paper Trading Pipeline
Integrates all 9 intelligence layers + Risk Manager + Trade Journal
Supports AUTO and MANUAL modes.
PAPER_TRADING=true always — no real money spent.
"""

import os
import sys
import json
import re
import time
import logging
import argparse
import glob
from datetime import datetime, timezone
from pathlib import Path

# Add TradingAgents to path
sys.path.insert(0, "/root/limitless-ai/TradingAgents")
sys.path.insert(0, "/root/limitless-ai")

from dotenv import load_dotenv
load_dotenv("/root/limitless-ai/TradingAgents/.env")

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.dataflows.alpaca_feed import get_current_price
from tradingagents.dataflows.mirofish_bridge import get_latest_mirofish_signal
from tradingagents.dataflows.run_logger import log_pipeline_run

from risk_manager import risk_check
from regime_detector import detect_regime
from trade_journal import log_decision
from mirofish_inline import ensure_fresh_signal

# ── Config ──────────────────────────────────────────────────────────────────
LOGS_DIR = Path("/root/limitless-ai/logs")
LOGS_DIR.mkdir(exist_ok=True)

TRADING_MODE = os.getenv("TRADING_MODE", "manual").lower()   # "auto" or "manual"
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
TICKER = "BTC-USD"
STARTING_BALANCE = 100_000.0
PORTFOLIO_FILE = LOGS_DIR / "portfolio.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Portfolio State ──────────────────────────────────────────────────────────
def load_portfolio():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {
        "cash": STARTING_BALANCE,
        "btc_units": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
    }

def save_portfolio(p):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)

# ── Knowledge Base ───────────────────────────────────────────────────────────
def load_knowledge_base():
    kb_dir = Path("/root/limitless-ai/knowledge_base")
    kb_text = ""
    files = sorted(glob.glob(str(kb_dir / "*.md")))
    for fp in files:
        try:
            content = open(fp).read()
            kb_text += f"\n\n### {Path(fp).stem.upper()}\n{content}"
        except Exception:
            pass
    if kb_text:
        logger.info(f"[KB] Loaded {len(files)} files ({len(kb_text)} chars) — Layer 9 active")
    return kb_text[:4000] if kb_text else ""

# ── Decision Parser ──────────────────────────────────────────────────────────
def parse_decision(final_state, regime="NEUTRAL", layer_count=0, bearish_count=0):
    """
    4-step cascade: structured protocol -> PM markdown rating -> decisive phrases -> fallback.
    Fixes HOLD bias caused by buy+sell both appearing in analysis text.
    
    REGIME SENSITIVITY: When market regime is BEAR (price below 20-day SMA) and 5+ layers 
    signal BEARISH or NEUTRAL, default action should be SELL with confidence proportional 
    to layer alignment:
    - 5/9 layers bearish: SELL at 65% confidence
    - 6/9 layers bearish: SELL at 72% confidence  
    - 7+ layers bearish: SELL at 80%+ confidence
    Do NOT default to HOLD when bearish signals dominate. HOLD means genuinely mixed signals.
    51% confidence indicates insufficient signal discrimination.
    """
    raw_parts = []
    ftd = final_state.get("final_trade_decision", "")
    if ftd:
        raw_parts.append(str(ftd))
    rds = final_state.get("risk_debate_state", {})
    if isinstance(rds, dict):
        jd = rds.get("judge_decision", "")
        if jd:
            raw_parts.append(str(jd))
    raw_decision = " ".join(raw_parts)

    if not raw_decision.strip():
        return "HOLD", 65

    # STEP 1: Structured PM_DECISION_PROTOCOL format — "Action: BUY"
    action_match = re.search(r'Action:\s*(STRONG_BUY|STRONG_SELL|BUY|SELL|HOLD)', raw_decision, re.IGNORECASE)
    conf_match   = re.search(r'Confidence:\s*(\d+)%?', raw_decision, re.IGNORECASE)
    if action_match:
        decision   = action_match.group(1).upper()
        confidence = int(conf_match.group(1)) if conf_match else 65
        return decision, max(51, min(95, confidence))

    # STEP 2: PM markdown heading — "Rating: **Sell**" / "Rating: Underweight"
    rating_match = re.search(
        r'Rating:\s*\*{0,2}(STRONG_BUY|STRONG_SELL|BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT)\*{0,2}',
        raw_decision, re.IGNORECASE
    )
    if rating_match:
        rating = rating_match.group(1).upper()
        rating_map = {"OVERWEIGHT": "BUY", "UNDERWEIGHT": "SELL"}
        decision   = rating_map.get(rating, rating)
        pct = re.search(r'(\d{2,3})%', raw_decision)
        confidence = int(pct.group(1)) if pct else 65
        return decision, max(51, min(95, confidence))

    # STEP 3: Decisive phrase matching (avoids buy+sell both-present -> HOLD)
    text_lower = raw_decision.lower()
    decisive_buy  = ["recommend buy", "strong buy", "clear buy", "initiate buy",
                     "go long", "purchase btc", "execute buy", "place buy"]
    decisive_sell = ["recommend sell", "strong sell", "clear sell", "initiate sell",
                     "go short", "sell btc", "execute sell", "place sell"]
    buy_hits  = sum(1 for p in decisive_buy  if p in text_lower)
    sell_hits = sum(1 for p in decisive_sell if p in text_lower)
    pct = re.search(r'(\d{2,3})%', raw_decision)
    conf_val = int(pct.group(1)) if pct else 65
    if buy_hits > sell_hits:
        return "BUY",  max(51, min(95, conf_val))
    if sell_hits > buy_hits:
        return "SELL", max(51, min(95, conf_val))

    # STEP 4: True fallback
    return "HOLD", 65

# ── Reasoning Extractor ──────────────────────────────────────────────────────
def extract_reasoning(final_state):
    """Extract a human-readable reasoning string from all agent layers."""
    parts = []

    td = final_state.get("final_trade_decision", "")
    if td:
        parts.append(f"Portfolio: {str(td)[:350]}")

    mr = final_state.get("market_report", "")
    if mr:
        parts.append(f"Market: {str(mr)[:150]}")

    nr = final_state.get("news_report", "")
    if nr:
        parts.append(f"News: {str(nr)[:150]}")

    rds = final_state.get("risk_debate_state", {})
    if isinstance(rds, dict):
        hist = rds.get("history", [])
        if hist:
            last = hist[-1] if isinstance(hist[-1], str) else str(hist[-1])
            parts.append(f"RiskDebate: {last[:150]}")

    return " || ".join(parts) if parts else "No detailed reasoning captured"

# ── Manual Mode Prompt ───────────────────────────────────────────────────────
def manual_confirm(decision, confidence, reasoning, price):
    """Prompt user to accept or override the AI decision."""
    print("\n" + "=" * 65)
    print(f"  🤖  AI DECISION : {decision}  ({confidence}% confidence)")
    print(f"  💰  BTC Price   : ${price:,.2f}")
    print(f"  🧠  Reasoning   : {reasoning[:280]}")
    print("=" * 65)
    print("  [A] Accept AI decision   [B] Force BUY   [S] Force SELL")
    print("  [H] Force HOLD           [X] Abort this cycle")
    print()
    try:
        choice = input("  Your choice: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        logger.info("[MANUAL] Non-interactive shell — accepting AI decision")
        return decision

    if choice == "B":
        return "BUY"
    elif choice == "S":
        return "SELL"
    elif choice == "H":
        return "HOLD"
    elif choice == "X":
        return None  # Abort
    else:
        return decision  # Default: accept AI


CALIBRATION_FILE = LOGS_DIR / "calibration_model.json"
CALIBRATION_MIN_SAMPLES = 50  # use calibrated confidence for risk gate after this many samples


def get_calibrated_confidence(raw_confidence, calibration_file=None):
    """
    Map raw PM confidence to isotonic-calibrated win probability.
    Returns (raw_confidence, calibrated_probability_or_None).
    Falls back to raw if model not available or too few samples.
    """
    if calibration_file is None:
        calibration_file = CALIBRATION_FILE
    try:
        with open(calibration_file) as f:
            model = json.load(f)
        curve = {p["raw_confidence"]: p["calibrated_probability"]
                 for p in model["calibration_curve"]}
        nearest = min(curve.keys(), key=lambda x: abs(x - raw_confidence))
        calibrated = curve[nearest]
        return raw_confidence, calibrated, model.get("training_samples", 0)
    except Exception:
        return raw_confidence, None, 0

# ── Main Cycle ───────────────────────────────────────────────────────────────
def run_cycle(cron_mode=False):
    logger.info("=" * 65)
    auto = cron_mode or (TRADING_MODE == "auto")
    logger.info(f"Limitless AI pipeline — Mode: {'AUTO' if auto else 'MANUAL'} | Paper: {PAPER_TRADING}")

    portfolio = load_portfolio()
    kb_context = load_knowledge_base()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Get live BTC price ──
    _t0_btc = time.time()
    try:
        price = get_current_price("BTC/USD")  # Alpaca uses BTC/USD not BTC-USD
        if not (1000 < price < 500_000):
            raise ValueError(f"BTC price sanity check failed: {price}")
        _btc_ms = int((time.time() - _t0_btc) * 1000)
        logger.info(f"[PRICE] BTC-USD: ${price:,.2f}")
        print(f"[DataFresh] BTC price fetched in {_btc_ms}ms: {price:.2f}")
    except Exception as e:
        logger.error(f"[PRICE] Failed: {e}")
        price = 0.0

    # ── MiroFish sentiment (Layer 4) ──
    # ── Auto-run MiroFish if signal is stale (>60 min) ──
    try:
        ensure_fresh_signal(max_age_minutes=60)
    except Exception as e:
        logger.warning(f"[MIROFISH:inline] Auto-run failed: {e}")

    mirofish = {}
    try:
        mirofish = get_latest_mirofish_signal() or {}
        if mirofish:
            logger.info(f"[MIROFISH] Label={mirofish.get('label','?')} Score={mirofish.get('score',0):.2f} Agents={mirofish.get('agents',0)}")
    except Exception as e:
        logger.warning(f"[MIROFISH] Unavailable: {e}")

    # ── Compute market regime (KMeans on 4h features) ──
    try:
        regime_result  = detect_regime()
        regime_name    = regime_result["regime"]   # BULL / BEAR / SIDEWAYS
        regime_conf    = regime_result["confidence"]
        regime_params  = regime_result["params"]
        _bias          = regime_params["bias"]
        _min_conf      = regime_params["confidence_threshold"]
        _pos_mult      = regime_params["position_size_multiplier"]
        regime_context = (
            chr(10) + chr(10) +
            f"MARKET REGIME: {regime_name} "
            f"(confidence={regime_conf:.0%}, stability={regime_result.get('stability', 0):.0%}). "
            f"Bias={_bias}. "
            f"Apply {_min_conf}% min confidence and {_pos_mult}x position sizing."
        )
        logger.info(f"[REGIME] {regime_name} | conf={regime_conf:.2f} | bias={_bias} | pos_mult={_pos_mult}x")
    except Exception as _re:
        logger.warning(f"[REGIME] detect_regime failed: {_re}")
        regime_name   = "SIDEWAYS"
        regime_params = {"confidence_threshold": 75, "position_size_multiplier": 0.6, "bias": "HOLD"}
        regime_context = ""

    # ── Build config with KB context ──
    from limitless_config import LIMITLESS_CONFIG
    from token_utils import compress_signal, log_context_size, count_tokens_approx
    run_config = dict(LIMITLESS_CONFIG)
    run_config["kb_context"] = kb_context
    run_config["mirofish"] = mirofish
    run_config["custom_context"] = run_config.get("custom_context", "") + compress_signal(regime_context)

    # ── Inject Elo weights into PM context ──
    try:
        from agent_elo import load_elo_state, get_elo_weights
        elo_state = load_elo_state()
        weights = get_elo_weights(elo_state["elos"])
        elo_text = "\n\nAGENT ELO WEIGHTS (updated after each resolved trade — use these to weight signals):\n"
        for layer, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            elo = elo_state["elos"][layer]
            elo_text += f"- {layer}: Elo {elo:.0f}, weight {weight:.3f}\n"
        n = elo_state.get("total_updates", 0)
        if n < 50:
            elo_text += f"\n(Note: Only {n} resolved trades so far — weights become meaningful at 50+. Treat as directional only.)\n"
        elo_text += "\nGive proportionally more weight to higher-Elo signals in your decision."
        run_config["custom_context"] += "\n\n" + compress_signal(elo_text)
        top_layer = sorted(weights.items(), key=lambda x: x[1], reverse=True)[0][0]
        logger.info(f"[ELO] Injected weights — {n} resolved trades, top layer: {top_layer}")
    except Exception as _elo_err:
        logger.warning(f"[ELO] Failed to inject weights: {_elo_err}")

    # -- Inject GDELT real-time geopolitical tone --
    try:
        from gdelt_client import get_gdelt_realtime_tone
        gdelt_result = get_gdelt_realtime_tone()
        if gdelt_result:
            gdelt_text = f"[L-GDELT] {gdelt_result['sentiment']} {gdelt_result['avg_tone']:.2f} | {gdelt_result['article_count']} articles | 4h"
            run_config["custom_context"] += "\n" + compress_signal(gdelt_text)
            logger.info(f"[GDELT] tone={gdelt_result['avg_tone']} sentiment={gdelt_result['sentiment']} articles={gdelt_result['article_count']}")
    except Exception as _gdelt_err:
        logger.warning(f"[GDELT] Failed to fetch tone: {_gdelt_err}")

    # === LAYER 10: KRONOS FINANCIAL TIME-SERIES ===
    try:
        import sys as _sys
        _sys.path.insert(0, "/root/limitless-ai")
        from kronos_signal import get_kronos_signal, fmt_kronos
        _kr = get_kronos_signal(lookback_bars=168)
        run_config["custom_context"] += "\n" + compress_signal(fmt_kronos(_kr))
        logger.info(f"[L10:Kronos] {_kr.get('signal','?')} {_kr.get('conf',0):.0%}")
    except Exception as _e:
        run_config["custom_context"] += "\n[L10:Kronos] UNAVAIL"
        logger.warning(f"[L10:Kronos] skip: {_e}")
    # === END L10 ===

    # === LAYER 11: POLYMARKET WHALE MONITOR (LOW RELIABILITY) ===
    try:
        from polymarket_whale_monitor import get_whale_signal, fmt_whale
        _wh = get_whale_signal(min_vol=50000, limit=20)
        run_config["custom_context"] += "\n" + fmt_whale(_wh)
        print(f"[L11:Whale] {_wh.get('signal','?')} {_wh.get('conf',0):.0%} [LOW TRUST]")
    except Exception as _e:
        run_config["custom_context"] += "\n[L11:Whale-LOW] UNAVAIL"
        print(f"[L11:Whale] skip: {_e}")
    # === END L11 ===

    # === LAYER 12: POLICY VOLATILITY DETECTOR ===
    try:
        from policy_volatility_signal import get_policy_signal, fmt_policy
        _pol = get_policy_signal()
        run_config["custom_context"] += "\n" + fmt_policy(_pol)
        print(f"[L12:Policy] {_pol.get('regime','?')} | events:{_pol.get('events',0)}")
        if _pol.get("regime") == "HIGH_VOLATILITY":
            print("[L12:Policy] ⚠️  RAISE PM THRESHOLD TO 70%")
    except Exception as _e:
        run_config["custom_context"] += "\n[L12:Policy] NORMAL | threshold:65%"
        print(f"[L12:Policy] skip: {_e}")
    # === END L12 ===

    # ── Token budget check ──
    log_context_size("pre-PM", run_config.get("custom_context", ""))
    if count_tokens_approx(run_config.get("custom_context", "")) > 4000:
        print(f"[Tokens:WARNING] {count_tokens_approx(run_config.get('custom_context', ''))} tokens — approaching limit")

    # ── Run TradingAgents (Layers 1-9) ──
    logger.info("[PIPELINE] Starting TradingAgents — all 9 intelligence layers...")
    try:
        ta = TradingAgentsGraph(debug=False, config=run_config)
        final_state, _agent_logs = ta.propagate(TICKER, today)
    except Exception as e:
        logger.error(f"[PIPELINE] Failed: {e}")
        import traceback; traceback.print_exc()
        return

    # ── Determine layer signals for regime sensitivity ──
    bearish_count = 0
    layer_count = 0
    # Count bearish signals from various sources
    if mirofish and mirofish.get("label") in ["BEARISH", "NEUTRAL"]:
        bearish_count += 1
        layer_count += 1
    # Add more layer analysis here as needed
    
    # Apply regime sensitivity if in BEAR market
    is_bear_regime = regime_name == "BEAR"
    
    # ── Parse decision ──
    decision, confidence = parse_decision(final_state, regime_name, layer_count, bearish_count)
    raw_confidence = confidence
    raw_conf, calibrated_conf, calib_samples = get_calibrated_confidence(confidence)
    if calibrated_conf is not None:
        logger.info(f"[CALIBRATION] raw={raw_confidence}% -> calibrated={calibrated_conf:.3f} (n={calib_samples})")
        if calib_samples >= CALIBRATION_MIN_SAMPLES:
            # Use calibrated probability (0-1 scale) converted to % for risk gate
            confidence = int(round(calibrated_conf * 100))
            logger.info(f"[CALIBRATION] Using calibrated confidence {confidence}% for risk gate (n={calib_samples}>=50)")
        else:
            logger.info(f"[CALIBRATION] Using raw confidence {confidence}% for risk gate (need {CALIBRATION_MIN_SAMPLES - calib_samples} more samples)")
    else:
        calibrated_conf = None
        logger.info("[CALIBRATION] No calibration model available, using raw confidence")
    reasoning = extract_reasoning(final_state)
    
    # REGIME SENSITIVITY: Override decision if BEAR regime with bearish signals
    if is_bear_regime and bearish_count >= 1:
        if bearish_count >= 3:  # Strong bearish alignment
            decision = "SELL"
            confidence = max(confidence, 80)
            logger.info(f"[REGIME] BEAR regime detected - overriding to SELL at {confidence}%")
        elif bearish_count >= 2:
            decision = "SELL"
            confidence = max(confidence, 72)
            logger.info(f"[REGIME] BEAR regime detected - overriding to SELL at {confidence}%")
    elif is_bear_regime:
        # At least adjust confidence upward when in bear market
        if confidence < 65 and decision == "HOLD":
            confidence = 65
            decision = "SELL"
            logger.info(f"[REGIME] BEAR regime - escalating HOLD to SELL at {confidence}%")
    logger.info(f"[DECISION] {decision} | {confidence}% confidence")
    logger.info(f"[REASONING] {reasoning[:200]}")

    signals = {
        "mirofish": mirofish,
        "analyst_summary": str(final_state.get("market_report", ""))[:300],
        "news_summary": str(final_state.get("news_report", ""))[:300],
        "fundamentals": str(final_state.get("fundamentals_report", ""))[:200],
        "risk_debate": str(final_state.get("risk_debate_state", ""))[:200],
        "kb_context_chars": len(kb_context),
    }

    # ── Manual confirmation ──
    is_trade = decision in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL")
    final_decision = decision

    if is_trade and not auto:
        final_decision = manual_confirm(decision, confidence, reasoning, price)
        if final_decision is None:
            logger.info("[MANUAL] Trade aborted by user")
            return

    # ── Risk check (BUY/SELL only) ──
    risk_result = {}
    if final_decision in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
        total_value = portfolio["cash"] + (portfolio["btc_units"] * price)
        portfolio_snap = {
            "initial_balance": STARTING_BALANCE,
            "current_balance": total_value,
            "cash": portfolio["cash"],
            "btc_units": portfolio["btc_units"],
            "price": price,
        }
        risk_passed, risk_reasoning, risk_result = risk_check(
            decision=final_decision,
            confidence=confidence,
            current_price=price,
            balance=total_value,
        )
        if not risk_passed:
            logger.warning(f"[RISK] BLOCKED — {risk_reasoning}")
            log_decision(
                symbol=TICKER,
                decision="BLOCKED",
                confidence=confidence,
                price=price,
                reasoning=reasoning,
                analyst_signals={"summary": signals.get("analyst_summary","")},
                mirofish_signal=mirofish if mirofish else None,
                portfolio_balance=total_value,
                risk_check_result=risk_result,
                kb_context_used=kb_context[:200],
            )
            log_pipeline_run(TICKER, price, "BLOCKED", confidence, reasoning, mirofish if mirofish else None, raw_confidence=raw_confidence, calibrated_confidence=calibrated_conf, regime=regime_name)
            return

    # ── Execute paper trade ──
    if final_decision in ("BUY", "STRONG_BUY") and portfolio["cash"] > 100:
        pct = 0.15 if final_decision == "STRONG_BUY" else 0.10
        amount_usd = portfolio["cash"] * pct
        btc_bought = amount_usd / price if price > 0 else 0
        portfolio["cash"] -= amount_usd
        portfolio["btc_units"] += btc_bought
        portfolio["total_trades"] += 1
        logger.info(f"[TRADE] PAPER BUY  ${amount_usd:,.2f} → {btc_bought:.6f} BTC @ ${price:,.2f}")

    elif final_decision in ("SELL", "STRONG_SELL") and portfolio["btc_units"] > 0:
        sell_units = portfolio["btc_units"] if final_decision == "STRONG_SELL" else portfolio["btc_units"] * 0.5
        amount_usd = sell_units * price
        portfolio["cash"] += amount_usd
        portfolio["btc_units"] -= sell_units
        portfolio["total_trades"] += 1
        logger.info(f"[TRADE] PAPER SELL {sell_units:.6f} BTC → ${amount_usd:,.2f} @ ${price:,.2f}")

    else:
        logger.info("[TRADE] HOLD — no position change")

    # ── Portfolio summary ──
    total_value = portfolio["cash"] + (portfolio["btc_units"] * price)
    pnl = total_value - STARTING_BALANCE
    logger.info(
        f"[PORTFOLIO] Cash=${portfolio['cash']:,.0f} | "
        f"BTC={portfolio['btc_units']:.4f} (${portfolio['btc_units']*price:,.0f}) | "
        f"Total=${total_value:,.0f} | P&L={'+' if pnl>=0 else ''}{pnl:,.0f}"
    )
    save_portfolio(portfolio)

    # ── Log everything ──
    log_decision(
        symbol=TICKER,
        decision=final_decision,
        confidence=confidence,
        price=price,
        reasoning=reasoning,
        analyst_signals={"summary": signals.get("analyst_summary","")},
        mirofish_signal=mirofish if mirofish else None,
        portfolio_balance=portfolio["cash"] + (portfolio["btc_units"] * price),
        risk_check_result=risk_result if risk_result else None,
        kb_context_used=kb_context[:200],
    )
    log_pipeline_run(TICKER, price, final_decision, confidence, reasoning, mirofish if mirofish else None, raw_confidence=raw_confidence, calibrated_confidence=calibrated_conf, regime=regime_name)
    logger.info(f"[DONE] {final_decision} @ ${price:,.2f} | {confidence}% | P&L ${pnl:+,.0f}")
    logger.info("=" * 65)


# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limitless AI Paper Trader")
    parser.add_argument("--cron", action="store_true", help="Cron mode — auto-execute without confirmation")
    parser.add_argument("--auto", action="store_true", help="Auto mode — same as cron")
    args = parser.parse_args()
    cron_mode = args.cron or args.auto or (TRADING_MODE == "auto")
    run_cycle(cron_mode=cron_mode)
