#!/usr/bin/env python3
"""
Limitless AI -- Multi-Asset Runner
Full pipeline for BTC, ETH, SOL: ATR stops, regime detection, per-asset
Telegram signal posts, per-asset log files, risk checks, ELO injection.
"""
import sys
import os
import json
import re
import glob
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

sys.path.insert(0, "/root/limitless-ai/TradingAgents")
sys.path.insert(0, "/root/limitless-ai")

from dotenv import load_dotenv
load_dotenv("/root/limitless-ai/TradingAgents/.env")

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.dataflows.alpaca_feed import get_current_price, get_atr
from tradingagents.dataflows.mirofish_bridge import get_latest_mirofish_signal
from tradingagents.dataflows.run_logger import log_pipeline_run
from risk_manager import risk_check
from regime_detector import detect_regime
from trade_journal import log_decision

# -- Telegram ------------------------------------------------------------------
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN_LIMITLESS", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_PRIVATE_CHAT   = os.getenv("TELEGRAM_CHAT_ID_LIMITLESS",   os.getenv("TELEGRAM_CHAT_ID", ""))
TELEGRAM_PUBLIC_CHANNEL = os.getenv("TELEGRAM_PUBLIC_CHANNEL_ID",   "@LimitlessAI_Signals")

# -- Paths ---------------------------------------------------------------------
LOGS_DIR = Path("/root/limitless-ai/logs")
LOGS_DIR.mkdir(exist_ok=True)

STARTING_BALANCE = 100_000.0
CALIBRATION_MIN_SAMPLES = 50

# -- Per-Asset Config ----------------------------------------------------------
ASSET_CONFIG = {
    "BTC-USD": {
        "alpaca":               "BTC/USD",
        "mirofish_weight":      1.0,
        "edgar_weight":         1.0,
        "confidence_threshold": 65,
        "log_file":             LOGS_DIR / "runs_btc.jsonl",
        "counter_file":         LOGS_DIR / "signal_counter_btc.json",
    },
    "ETH-USD": {
        "alpaca":               "ETH/USD",
        "mirofish_weight":      0.8,
        "edgar_weight":         1.2,   # ETH ETF narrative correlates with EDGAR filings
        "confidence_threshold": 68,
        "log_file":             LOGS_DIR / "runs_eth.jsonl",
        "counter_file":         LOGS_DIR / "signal_counter_eth.json",
    },
    "SOL-USD": {
        "alpaca":               "SOL/USD",
        "mirofish_weight":      1.3,   # SOL is retail-sentiment driven
        "edgar_weight":         0.7,
        "confidence_threshold": 70,    # higher threshold -- more volatile, more noise
        "log_file":             LOGS_DIR / "runs_sol.jsonl",
        "counter_file":         LOGS_DIR / "signal_counter_sol.json",
    },
}

# -- Decision Parser (4-step cascade, ported from run_paper_trade.py) ----------
def parse_decision(final_state, regime="NEUTRAL", layer_count=0, bearish_count=0):
    """
    4-step cascade: structured protocol -> PM markdown rating ->
    decisive phrases -> fallback. Avoids HOLD bias from buy+sell both present.
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

    # STEP 1: Structured format -- "Action: BUY"
    action_match = re.search(r'Action:\s*(STRONG_BUY|STRONG_SELL|BUY|SELL|HOLD)', raw_decision, re.IGNORECASE)
    conf_match   = re.search(r'Confidence:\s*(\d+)%?', raw_decision, re.IGNORECASE)
    if action_match:
        decision   = action_match.group(1).upper()
        confidence = int(conf_match.group(1)) if conf_match else 65
        return decision, max(51, min(95, confidence))

    # STEP 2: PM markdown rating -- "Rating: **Sell**"
    rating_match = re.search(
        r'Rating:\s*\*{0,2}(STRONG_BUY|STRONG_SELL|BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT)\*{0,2}',
        raw_decision, re.IGNORECASE,
    )
    if rating_match:
        rating     = rating_match.group(1).upper()
        decision   = {"OVERWEIGHT": "BUY", "UNDERWEIGHT": "SELL"}.get(rating, rating)
        pct        = re.search(r'(\d{2,3})%', raw_decision)
        confidence = int(pct.group(1)) if pct else 65
        return decision, max(51, min(95, confidence))

    # STEP 3: Decisive phrase matching
    text_lower    = raw_decision.lower()
    decisive_buy  = ["recommend buy", "strong buy", "clear buy", "initiate buy",
                     "go long", "execute buy", "place buy"]
    decisive_sell = ["recommend sell", "strong sell", "clear sell", "initiate sell",
                     "go short", "execute sell", "place sell"]
    buy_hits  = sum(1 for p in decisive_buy  if p in text_lower)
    sell_hits = sum(1 for p in decisive_sell if p in text_lower)
    pct       = re.search(r'(\d{2,3})%', raw_decision)
    conf_val  = int(pct.group(1)) if pct else 65
    if buy_hits > sell_hits:
        return "BUY",  max(51, min(95, conf_val))
    if sell_hits > buy_hits:
        return "SELL", max(51, min(95, conf_val))

    # STEP 4: Fallback
    return "HOLD", 65


def extract_reasoning(final_state):
    parts = []
    td = final_state.get("final_trade_decision", "")
    if td:
        parts.append(f"Portfolio: {str(td)[:300]}")
    mr = final_state.get("market_report", "")
    if mr:
        parts.append(f"Market: {str(mr)[:150]}")
    nr = final_state.get("news_report", "")
    if nr:
        parts.append(f"News: {str(nr)[:150]}")
    return " || ".join(parts) if parts else "No reasoning captured"


# -- Signal Counter ------------------------------------------------------------
def get_next_signal_number(counter_file):
    counter = {"n": 0}
    if counter_file.exists():
        try:
            with open(counter_file) as f:
                counter = json.load(f)
        except Exception:
            pass
    counter["n"] += 1
    with open(counter_file, "w") as f:
        json.dump(counter, f)
    return counter["n"]


# -- Telegram helpers ----------------------------------------------------------
def _send_telegram(text, chat_id, parse_mode="HTML"):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning(f"Telegram not configured (chat_id={chat_id!r})")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(f"Telegram HTTP {r.status_code}: {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def post_to_public_channel(symbol, decision, confidence, price, regime,
                            signal_n, key_layer="", dry_run=False):
    """Post a formatted signal to @LimitlessAI_Signals public channel."""
    ticker = symbol.replace("-USD", "")
    action = decision.replace("STRONG_", "")
    emoji  = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(action, "⚪")
    msg = (
        f"{emoji} <b>{ticker} {decision}</b> -- Signal #{signal_n}\n"
        f"💰 {ticker}/USD: ${price:,.2f}\n"
        f"📊 Confidence: {confidence}%\n"
        f"🌍 Regime: {regime}\n"
    )
    if key_layer:
        msg += f"🔑 {key_layer}\n"
    msg += "\nt.me/LimitlessAI_Signals"

    if dry_run:
        logger.info(f"[DRY-RUN] Public channel post for {ticker}:\n{msg}")
        return True
    ok = _send_telegram(msg, TELEGRAM_PUBLIC_CHANNEL)
    logger.info(f"[{ticker}] Public channel post: {'OK' if ok else 'FAILED'}")
    return ok


# -- Knowledge Base ------------------------------------------------------------
def load_knowledge_base():
    kb_dir = Path("/root/limitless-ai/knowledge_base")
    kb_text = ""
    for fp in sorted(glob.glob(str(kb_dir / "*.md"))):
        try:
            kb_text += f"\n\n### {Path(fp).stem.upper()}\n{open(fp).read()}"
        except Exception:
            pass
    if kb_text:
        logger.info(f"[KB] {len(kb_text)} chars loaded")
    return kb_text[:4000] if kb_text else ""


# -- Per-Asset Pipeline --------------------------------------------------------
def run_asset(symbol, cron_mode=False, dry_run=False):
    cfg    = ASSET_CONFIG.get(symbol)
    ticker = symbol.replace("-USD", "")

    if not cfg:
        logger.error(f"Unknown symbol: {symbol}")
        return None

    logger.info("=" * 60)
    logger.info(f"[{ticker}] Starting analysis | cron={cron_mode} dry_run={dry_run}")

    # -- Price --
    try:
        price = get_current_price(cfg["alpaca"])
        logger.info(f"[{ticker}] Price: ${price:,.2f}")
    except Exception as e:
        logger.error(f"[{ticker}] Price fetch failed: {e}")
        return None

    # -- MiroFish (per-asset weight applied) --
    mirofish = {}
    try:
        raw_mf = get_latest_mirofish_signal() or {}
        if raw_mf:
            mirofish = dict(raw_mf)
            w = cfg["mirofish_weight"]
            if "score" in mirofish:
                mirofish["score"]          = round(mirofish["score"] * w, 4)
                mirofish["weight_applied"] = w
            logger.info(
                f"[{ticker}] MiroFish: {mirofish.get('label')} "
                f"score={mirofish.get('score', 0):.2f} (weight={w}x)"
            )
    except Exception as e:
        logger.warning(f"[{ticker}] MiroFish unavailable: {e}")

    # -- Regime (BTC as crypto macro indicator) --
    regime_name   = "SIDEWAYS"
    regime_conf   = 0.5
    regime_params = {"confidence_threshold": 75, "position_size_multiplier": 0.6, "bias": "HOLD"}
    try:
        regime_result = detect_regime()
        regime_name   = regime_result["regime"]
        regime_conf   = regime_result["confidence"]
        regime_params = regime_result["params"]
        logger.info(
            f"[{ticker}] Regime: {regime_name} conf={regime_conf:.2f} "
            f"bias={regime_params['bias']}"
        )
    except Exception as e:
        logger.warning(f"[{ticker}] Regime detection failed: {e}")

    # -- ATR stop --
    atr_stop     = None
    atr_stop_pct = None
    try:
        atr_result = get_atr(cfg["alpaca"])
        atr = float(atr_result["atr_usd"]) if isinstance(atr_result, dict) else float(atr_result)
        if atr and price:
            raw_pct      = (2.0 * atr) / price * 100
            atr_stop_pct = round(max(1.5, min(5.0, raw_pct)), 2)
            atr_stop     = round(price * (1 - atr_stop_pct / 100), 2)
            logger.info(f"[{ticker}] ATR stop: ${atr_stop:,.2f} ({atr_stop_pct:.1f}% below entry)")
    except Exception as e:
        logger.warning(f"[{ticker}] ATR stop calc failed: {e}")

    # -- Build run config --
    kb_context = load_knowledge_base()
    regime_context = (
        f"\n\nMARKET REGIME: {regime_name} "
        f"(confidence={regime_conf:.0%}, bias={regime_params['bias']}). "
        f"Min confidence threshold: {regime_params['confidence_threshold']}%."
    )
    asset_context = ""
    if cfg["edgar_weight"] != 1.0:
        desc = "institutional ETF filing correlation -- weight higher" if cfg["edgar_weight"] > 1 else "lower institutional relevance"
        asset_context += f"\n\nEDGAR FILING WEIGHT FOR {ticker}: {cfg['edgar_weight']}x ({desc})."
    if cfg["mirofish_weight"] != 1.0:
        desc = "retail-driven asset -- weight higher" if cfg["mirofish_weight"] > 1 else "less retail-sentiment sensitive"
        asset_context += f"\nMIROFISH SENTIMENT WEIGHT FOR {ticker}: {cfg['mirofish_weight']}x ({desc})."

    run_config = {
        "kb_context":        kb_context,
        "mirofish":          mirofish,
        "custom_context":    regime_context + asset_context,
        "max_debate_rounds": 1,
        "online_tools":      True,
    }

    # Try loading LIMITLESS_CONFIG base
    try:
        from limitless_config import LIMITLESS_CONFIG
        base = dict(LIMITLESS_CONFIG)
        base.update(run_config)
        run_config = base
    except Exception:
        pass

    # -- ELO weights --
    try:
        from agent_elo import load_elo_state, get_elo_weights
        elo_state = load_elo_state()
        weights   = get_elo_weights(elo_state["elos"])
        elo_text  = "\n\nAGENT ELO WEIGHTS (top 5):\n"
        for layer, w in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:5]:
            elo_text += f"- {layer}: weight {w:.3f}\n"
        n = elo_state.get("total_updates", 0)
        if n < CALIBRATION_MIN_SAMPLES:
            elo_text += f"(Only {n} resolved trades -- treat as directional.)\n"
        run_config["custom_context"] += elo_text
        logger.info(f"[{ticker}] ELO weights injected (n={n})")
    except Exception as e:
        logger.warning(f"[{ticker}] ELO inject failed: {e}")

    # -- GDELT --
    try:
        from gdelt_client import get_gdelt_realtime_tone
        gdelt = get_gdelt_realtime_tone()
        if gdelt:
            run_config["custom_context"] += (
                f"\nGDELT Geopolitical Tone: {gdelt['avg_tone']} = {gdelt['sentiment']} "
                f"({gdelt['article_count']} articles)"
            )
            logger.info(f"[{ticker}] GDELT tone={gdelt['avg_tone']} sentiment={gdelt['sentiment']}")
    except Exception as e:
        logger.warning(f"[{ticker}] GDELT failed: {e}")

    # -- TradingAgents --
    logger.info(f"[{ticker}] Running TradingAgents pipeline...")
    try:
        ta = TradingAgentsGraph(debug=False, config=run_config)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        final_state, _ = ta.propagate(symbol, today)
    except Exception as e:
        logger.error(f"[{ticker}] Pipeline failed: {e}")
        import traceback; traceback.print_exc()
        return None

    # -- Parse decision --
    decision, confidence = parse_decision(final_state, regime_name)
    reasoning            = extract_reasoning(final_state)

    # Apply per-asset + regime confidence threshold
    min_conf = max(cfg["confidence_threshold"], regime_params.get("confidence_threshold", 65))
    if confidence < min_conf and decision in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL"):
        logger.info(
            f"[{ticker}] Confidence {confidence}% < threshold {min_conf}% -- downgrading to HOLD"
        )
        decision = "HOLD"

    # Bear regime override (mirrors run_paper_trade.py logic)
    bearish_mf = bool(mirofish) and mirofish.get("label") in ("BEARISH", "NEUTRAL")
    if regime_name == "BEAR":
        if bearish_mf:
            decision   = "SELL"
            confidence = max(confidence, 72)
            logger.info(f"[{ticker}] BEAR + bearish MiroFish -> SELL @ {confidence}%")
        elif decision == "HOLD" and confidence < 65:
            decision   = "SELL"
            confidence = 65
            logger.info(f"[{ticker}] BEAR regime escalating HOLD -> SELL @ {confidence}%")

    logger.info(f"[{ticker}] Decision: {decision} @ {confidence}%")

    # -- Risk check --
    risk_result = {}
    if decision in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL") and not dry_run:
        try:
            risk_passed, risk_reason, risk_result = risk_check(
                decision=decision,
                confidence=confidence,
                current_price=price,
                balance=STARTING_BALANCE,
            )
            if not risk_passed:
                logger.warning(f"[{ticker}] RISK BLOCKED: {risk_reason}")
                decision = "BLOCKED"
        except Exception as e:
            logger.warning(f"[{ticker}] Risk check skipped: {e}")

    # -- Key layer summary for Telegram --
    key_layer = ""
    mf_label  = mirofish.get("label", "")
    if mf_label:
        key_layer = f"MiroFish: {mf_label}"
    if not key_layer:
        mr = str(final_state.get("market_report", ""))[:80].strip()
        if mr:
            key_layer = mr

    # -- Post to public channel (BUY/SELL only) --
    if decision in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
        signal_n = get_next_signal_number(cfg["counter_file"]) if not dry_run else 0
        post_to_public_channel(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            price=price,
            regime=regime_name,
            signal_n=signal_n,
            key_layer=key_layer,
            dry_run=dry_run,
        )

    # -- Log to per-asset file --
    record = {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "symbol":        symbol,
        "price":         price,
        "decision":      decision,
        "confidence":    confidence,
        "regime":        regime_name,
        "atr_stop":      atr_stop,
        "atr_stop_pct":  atr_stop_pct,
        "mirofish":      mirofish,
        "risk_result":   risk_result,
        "reasoning":     reasoning[:400],
    }
    if not dry_run:
        with open(cfg["log_file"], "a") as f:
            f.write(json.dumps(record) + "\n")

        # Unified dashboard log
        log_pipeline_run(
            asset=symbol,
            price=price,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            mirofish_result=mirofish if mirofish else None,
            regime=regime_name,
        )

        # Trade journal
        try:
            log_decision(
                symbol=symbol,
                decision=decision,
                confidence=confidence,
                price=price,
                reasoning=reasoning,
                analyst_signals={"summary": str(final_state.get("market_report", ""))[:300]},
                mirofish_signal=mirofish if mirofish else None,
                portfolio_balance=STARTING_BALANCE,
                risk_check_result=risk_result if risk_result else None,
                kb_context_used=kb_context[:200],
            )
        except Exception as e:
            logger.warning(f"[{ticker}] log_decision failed: {e}")

    logger.info(f"[{ticker}] Done -- {decision} @ ${price:,.2f} | {confidence}%")
    return record


# -- Summary -------------------------------------------------------------------
def print_summary(results):
    print("\n" + "=" * 62)
    print("  LIMITLESS AI -- MULTI-ASSET ANALYSIS")
    print("=" * 62)
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("-" * 62)
    for r in results:
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "BLOCKED": "🚫"}.get(r["decision"], "⚪")
        stop  = f"  stop=${r['atr_stop']:,.2f} ({r['atr_stop_pct']}%)" if r.get("atr_stop") else ""
        print(
            f"  {emoji} {r['symbol']:9} | ${r['price']:>12,.2f} | "
            f"{r['decision']:10} @ {r['confidence']}%{stop}"
        )
    print("=" * 62 + "\n")


# -- Entry Point ---------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limitless AI Multi-Asset Runner")
    parser.add_argument("--asset",   help="Single asset (BTC-USD, ETH-USD, SOL-USD)")
    parser.add_argument("--cron",    action="store_true", help="Cron/auto mode")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Show decisions, skip execution and Telegram posts")
    args = parser.parse_args()

    if args.asset:
        sym = args.asset.upper()
        if not sym.endswith("-USD"):
            sym += "-USD"
        symbols = [sym]
    else:
        symbols = list(ASSET_CONFIG.keys())

    results = []
    for sym in symbols:
        result = run_asset(sym, cron_mode=args.cron, dry_run=args.dry_run)
        if result:
            results.append(result)

    if results:
        print_summary(results)
