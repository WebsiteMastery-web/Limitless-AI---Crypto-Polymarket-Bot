#!/usr/bin/env python3
"""
run_backtest.py - Historical backtesting for Limitless AI trading system.
Usage:
  python3 run_backtest.py              # 7-day backtest
  python3 run_backtest.py --days 30   # 30-day backtest  
  python3 run_backtest.py --fast      # 1 debate round (cost-optimized)
  python3 run_backtest.py --batch     # Random sample from past year
"""
import argparse
import datetime
import json
import logging
import os
import random
import sys
import time

import requests

sys.path.insert(0, '/root/limitless-ai')
sys.path.insert(0, '/root/limitless-ai/TradingAgents')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Limitless AI Backtest')
parser.add_argument('--days', type=int, default=7, help='Number of days to backtest (default: 7)')
parser.add_argument('--fast', action='store_true', help='Fast mode: 1 debate round (saves API cost)')
parser.add_argument('--batch', action='store_true', help='Batch mode: random sample from past year')
parser.add_argument('--ticker', type=str, default='BTC-USD', help='Ticker to backtest (default: BTC-USD)')
args = parser.parse_args()

TICKER = args.ticker
FAST_MODE = args.fast
LOG_FILE = '/root/limitless-ai/logs/backtest_results.jsonl'
os.makedirs('/root/limitless-ai/logs', exist_ok=True)

# Build list of dates to backtest
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

if args.batch:
    # Random sample of 10 dates from past year
    start = today - datetime.timedelta(days=365)
    all_days = [start + datetime.timedelta(days=i) for i in range(365)]
    dates_to_run = sorted(random.sample(all_days, min(10, len(all_days))))
elif args.days:
    dates_to_run = [yesterday - datetime.timedelta(days=i) for i in range(args.days)]
    dates_to_run.sort()
else:
    dates_to_run = [yesterday]

logger.info(f"Running {len(dates_to_run)} backtest(s)...")
logger.info(f"Mode: {'FAST (1 debate round)' if FAST_MODE else 'NORMAL (2 debate rounds)'}")
logger.info(f"Dates: {[str(d) for d in dates_to_run]}")

# Apply fast mode config
if FAST_MODE:
    try:
        from TradingAgents import limitless_config
        limitless_config.max_debate_rounds = 1
        logger.info("Fast mode: max_debate_rounds set to 1")
    except Exception as e:
        logger.warning(f"Could not apply fast mode config: {e}")

# Load the TradingAgents pipeline
try:
    from TradingAgents.graph.trading_graph import TradingAgentsGraph
    from TradingAgents.limitless_config import LIMITLESS_CONFIG, SELECTED_ANALYSTS
    ta = TradingAgentsGraph(debug=False, config=LIMITLESS_CONFIG, selected_analysts=SELECTED_ANALYSTS)
    logger.info("TradingAgents pipeline loaded")
except Exception as e:
    logger.error(f"Failed to load TradingAgents: {e}")
    sys.exit(1)

def get_historical_price(ticker, target_date):
    """Fetch historical closing price for a given date."""
    try:
        import copy
        date_str = target_date.strftime('%Y-%m-%d')
        end_date = target_date + datetime.timedelta(days=1)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            'period1': int(datetime.datetime.combine(target_date, datetime.time.min).timestamp()),
            'period2': int(datetime.datetime.combine(end_date, datetime.time.min).timestamp()),
            'interval': '1d'
        }
        resp = requests.get(url, params=params, timeout=10,
                           headers={'User-Agent': 'Mozilla/5.0'})
        data = resp.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        price = closes[0] if closes else None
        return price
    except Exception as e:
        logger.warning(f"Could not fetch price for {target_date}: {e}")
        return None

def parse_decision(final_state):
    """Parse TradingAgents output into structured decision."""
    # LangGraph may return (state, metadata) tuple
    if isinstance(final_state, (tuple, list)):
        final_state = final_state[0] if final_state else {}
    if not isinstance(final_state, dict):
        final_state = {}

    raw_text = ""
    ftd = final_state.get("final_trade_decision", "")
    if isinstance(ftd, str):
        raw_text += ftd
    rds = final_state.get("risk_debate_state", {})
    if isinstance(rds, dict):
        for k in ("bull_argument", "bear_argument", "judge_decision"):
            v = rds.get(k, "")
            if isinstance(v, str):
                raw_text += " " + v

    import re
    text = raw_text.lower()

    if re.search(r'strong\s*buy|aggressively\s*buy|very\s*bullish', text):
        decision, confidence = "STRONG_BUY", 80
    elif re.search(r'overweight|outperform|buy|bullish|long\s*position|increase.*position', text):
        decision, confidence = "BUY", 70
    elif re.search(r'strong\s*sell|aggressively\s*sell|very\s*bearish', text):
        decision, confidence = "STRONG_SELL", 80
    elif re.search(r'underweight|underperform|sell|bearish|short\s*position|reduce.*position|exit', text):
        decision, confidence = "SELL", 70
    else:
        decision, confidence = "HOLD", 60

    return decision, confidence, raw_text[:500]

results = []
wins = 0
total_evaluated = 0

for i, date_str in enumerate(dates_to_run):
    logger.info(f"\n{'='*50}")
    logger.info(f"Backtesting date: {date_str} ({i+1}/{len(dates_to_run)})")

    # Get entry price (price at signal date)
    entry_price = get_historical_price(TICKER, date_str)
    if not entry_price:
        logger.warning(f"Skipping {date_str} - no price data")
        continue
    logger.info(f"Entry price: ${entry_price:,.2f}")

    # Run the AI pipeline for that date
    try:
        final_state = ta.propagate(TICKER, str(date_str))
        # Unwrap tuple if needed
        if isinstance(final_state, (tuple, list)):
            final_state = final_state[0] if final_state else {}
        decision, confidence, reasoning = parse_decision(final_state)
        logger.info(f"Decision: {decision} | Confidence: {confidence}%")
    except Exception as e:
        logger.error(f"Pipeline error for {date_str}: {e}")
        continue

    # Get exit price (next trading day)
    exit_date = date_str + datetime.timedelta(days=1)
    exit_price = get_historical_price(TICKER, exit_date)

    # Calculate accuracy
    pct_4h = 0.0
    correct = None
    if exit_price and entry_price:
        pct_4h = (exit_price - entry_price) / entry_price * 100
        if decision in ("BUY", "STRONG_BUY"):
            correct = pct_4h > 1.0
        elif decision in ("SELL", "STRONG_SELL"):
            correct = pct_4h < -1.0
        else:  # HOLD
            correct = abs(pct_4h) < 3.0

        if correct:
            wins += 1
        total_evaluated += 1
        logger.info(f"Next-day change: {pct_4h:+.2f}% | Correct: {correct}")

    result = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "backtest_date": str(date_str),
        "ticker": TICKER,
        "price_at_decision": entry_price,
        "decision": decision,
        "confidence": confidence,
        "reasoning_snippet": reasoning[:200],
        "outcome_4h_pct": round(pct_4h, 3),
        "correct": correct,
        "fast_mode": FAST_MODE,
    }
    results.append(result)

    # Save incrementally
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(result) + '\n')

    logger.info(f"Result saved to {LOG_FILE}")

    # Rate limit between runs
    if i < len(dates_to_run) - 1:
        wait_time = 30 if FAST_MODE else 60
        logger.info(f"Waiting {wait_time}s before next backtest...")
        time.sleep(wait_time)

# Final summary
accuracy = (wins / total_evaluated * 100) if total_evaluated > 0 else 0
logger.info(f"\n{'='*60}")
logger.info(f"BACKTEST COMPLETE")
logger.info(f"Dates tested: {total_evaluated}/{len(dates_to_run)}")
logger.info(f"Wins: {wins} | Accuracy: {accuracy:.1f}%")
logger.info(f"Results saved to: {LOG_FILE}")

summary = {
    "total_dates": total_evaluated,
    "wins": wins,
    "accuracy_pct": round(accuracy, 1),
    "ticker": TICKER,
    "fast_mode": FAST_MODE,
}
logger.info(f"Summary: {json.dumps(summary)}")
