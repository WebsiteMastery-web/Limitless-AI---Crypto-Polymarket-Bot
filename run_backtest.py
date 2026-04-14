"""
Limitless AI — Backtester with Outcome Tracking
Fetches historical BTC price + date-filtered news into the full 9-layer pipeline,
gets a BUY/HOLD/SELL decision, then scores it against actual next-day price movement.
Usage: python run_backtest.py --days 30
       python run_backtest.py --date 2026-02-15
       python run_backtest.py --batch 50
       python run_backtest.py --batch-250  # Run 250 random dates from past 18 months
"""

import sys, os, json, time, argparse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/limitless-ai/TradingAgents")
from dotenv import load_dotenv

load_dotenv("/root/limitless-ai/TradingAgents/.env")
from loguru import logger

BACKTEST_LOG = "/root/limitless-ai/logs/backtest_results.jsonl"
BACKTEST_SUMMARY = "/root/limitless-ai/logs/backtest_summary.json"
os.makedirs("/root/limitless-ai/logs", exist_ok=True)

args_fast = False
args_batch_250 = False


def get_btc_next_day_price(date_str: str) -> dict:
    """Get BTC-USD close price on decision date and next day using yfinance."""
    try:
        import yfinance as yf

        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_date = (dt - timedelta(days=2)).strftime("%Y-%m-%d")
        end_date = (dt + timedelta(days=3)).strftime("%Y-%m-%d")

        btc = yf.download("BTC-USD", start=start_date, end=end_date, progress=False)
        if btc.empty or len(btc) < 2:
            return {}

        if hasattr(btc.columns, "droplevel"):
            btc.columns = btc.columns.droplevel(1)

        btc = btc.reset_index()

        price_d = None
        price_d1 = None

        for i, row in enumerate(btc.itertuples()):
            row_date = (
                row.Date.strftime("%Y-%m-%d")
                if hasattr(row, "Date")
                else str(btc.index[i])[:10]
            )
            if row_date == date_str:
                price_d = float(row.Close)
            next_day_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            if row_date == next_day_date:
                price_d1 = float(row.Close)
                break

        if price_d is None and len(btc) >= 1:
            price_d = float(btc.iloc[0]["Close"])
        if price_d1 is None and len(btc) >= 2:
            price_d1 = float(btc.iloc[1]["Close"])

        if price_d and price_d1:
            return {
                "price_at_decision": price_d,
                "price_next_day": price_d1,
                "price_fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        return {}

        btc = btc.reset_index()
        prices = btc["Close"].values

        price_d = None
        price_d1 = None

        for i, row in enumerate(btc.itertuples()):
            row_date = (
                row.Date.strftime("%Y-%m-%d")
                if hasattr(row, "Date")
                else str(btc.index[i])[:10]
            )
            if row_date == date_str:
                price_d = float(prices[i])
            next_day_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            if row_date == next_day_date:
                price_d1 = float(prices[i])
                break

        if price_d is None and len(prices) >= 1:
            price_d = float(prices[0])
        if price_d1 is None and len(prices) >= 2:
            price_d1 = float(prices[1])

        if price_d and price_d1:
            return {
                "price_at_decision": price_d,
                "price_next_day": price_d1,
                "price_fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        return {}

    except Exception as e:
        logger.warning(f"yfinance price fetch failed: {e}")
        return {}


def calculate_outcome(decision: str, price_d: float, price_d1: float) -> dict:
    """Calculate outcome based on decision and next-day price movement."""
    if decision in ("HOLD", "BLOCKED", "ERROR", None) or not price_d or not price_d1:
        return {"outcome": "N/A", "outcome_pct": None}

    pct_change = (price_d1 - price_d) / price_d * 100

    if decision == "BUY":
        if pct_change > 0:
            return {"outcome": "WIN", "outcome_pct": round(pct_change, 3)}
        else:
            return {"outcome": "LOSS", "outcome_pct": round(pct_change, 3)}
    elif decision == "SELL":
        if pct_change < 0:
            return {"outcome": "WIN", "outcome_pct": round(abs(pct_change), 3)}
        else:
            return {"outcome": "LOSS", "outcome_pct": round(-pct_change, 3)}

    return {"outcome": "N/A", "outcome_pct": None}


def get_historical_price(date_str: str, symbol: str = "BTC/USD") -> dict:
    """Get BTC OHLCV for a specific date via Alpaca."""
    try:
        from alpaca.data.historical import CryptoHistoricalDataClient
        from alpaca.data.requests import CryptoBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = CryptoHistoricalDataClient()
        start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = start + timedelta(days=2)
        req = CryptoBarsRequest(
            symbol_or_symbols=symbol, timeframe=TimeFrame.Hour, start=start, end=end
        )
        bars = client.get_crypto_bars(req)
        df = bars.df
        if df.empty:
            return {}
        prices = df["close"].values
        return {
            "open": float(prices[0]),
            "price_4h": float(prices[3]) if len(prices) > 3 else float(prices[-1]),
            "price_8h": float(prices[7]) if len(prices) > 7 else float(prices[-1]),
            "price_24h": float(prices[23]) if len(prices) > 23 else float(prices[-1]),
            "price_72h": float(prices[71]) if len(prices) > 71 else float(prices[-1]),
        }
    except Exception as e:
        logger.warning(f"Historical price fetch failed: {e}")
        return {}


def get_historical_news(date_str: str) -> str:
    """Get news headlines for a specific past date via GDELT."""
    try:
        import requests

        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt_end = dt + timedelta(days=1)
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": "bitcoin cryptocurrency BTC market",
            "mode": "artlist",
            "maxrecords": "10",
            "startdatetime": dt.strftime("%Y%m%d%H%M%S"),
            "enddatetime": dt_end.strftime("%Y%m%d%H%M%S"),
            "format": "json",
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            articles = data.get("articles", [])
            if articles:
                lines = [f"=== HISTORICAL NEWS FOR {date_str} (GDELT) ==="]
                for a in articles[:8]:
                    lines.append(f"- {a.get('title', 'No title')} ({a.get('url', '')})")
                logger.info(
                    f"GDELT: fetched {len(articles)} historical articles for {date_str}"
                )
                return "\n".join(lines)
        return (
            f"Historical news unavailable for {date_str} — using current signals only"
        )
    except Exception as e:
        logger.warning(f"Historical news fetch failed: {e}")
        return f"Historical news unavailable: {e}"


def run_single_backtest(date_str: str) -> dict:
    """Run one backtest for a specific date. Returns scored result with outcome tracking."""
    logger.info(f"Backtesting date: {date_str}")

    prices = get_historical_price(date_str)
    if not prices:
        logger.warning(f"No price data for {date_str}, skipping")
        return {}
    entry_price = prices["open"]
    logger.info(f"BTC open price on {date_str}: ${entry_price:,.2f}")

    historical_news = get_historical_news(date_str)

    os.environ["BACKTEST_DATE"] = date_str
    os.environ["BACKTEST_PRICE"] = str(entry_price)
    os.environ["BACKTEST_NEWS"] = historical_news

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from limitless_config import LIMITLESS_CONFIG
        import copy as _copy

        if args_fast:
            _fast_cfg = _copy.deepcopy(LIMITLESS_CONFIG)
            _fast_cfg["max_debate_rounds"] = 1
            _fast_cfg["max_risk_discuss_rounds"] = 1
            LIMITLESS_CONFIG = _fast_cfg
        graph = TradingAgentsGraph(config=LIMITLESS_CONFIG)
        result, _ = graph.propagate(f"BTC-USD", date_str)
        # Parse final_trade_decision text for actual decision
        ftd = str(result.get("final_trade_decision") or "")
        reasoning = ftd[:500]
        # Extract decision from text
        import re as _re
        _dec_match = _re.search(r"Rating:\s*\*{0,2}(Buy|Sell|Hold|Overweight|Underweight)", ftd, _re.IGNORECASE)
        if _dec_match:
            _raw = _dec_match.group(1).upper()
            decision = {"OVERWEIGHT": "BUY", "UNDERWEIGHT": "SELL", "BUY": "BUY", "SELL": "SELL"}.get(_raw, "HOLD")
        else:
            decision = result.get("action") or result.get("trade_type") or "HOLD"
        # Extract confidence from text
        _conf_match = _re.search(r"(?:confidence|conviction)[:\s]+(?:level\s+(?:of\s+)?)?(?:\*{0,2})(\d+)(?:/10|%)", ftd, _re.IGNORECASE)
        if _conf_match:
            _cv = int(_conf_match.group(1))
            confidence = _cv * 10 if _cv <= 10 else _cv
        else:
            confidence = int(result.get("confidence", 50))
    except Exception as e:
        logger.error(f"Pipeline failed for {date_str}: {e}")
        decision = "ERROR"
        confidence = 0
        reasoning = str(e)

    price_data = get_btc_next_day_price(date_str)

    if price_data:
        outcome_data = calculate_outcome(
            decision,
            price_data.get("price_at_decision"),
            price_data.get("price_next_day"),
        )
    else:
        outcome_data = {"outcome": "N/A", "outcome_pct": None}
        price_data = {
            "price_at_decision": entry_price,
            "price_next_day": None,
            "price_fetch_date": None,
        }

    result_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backtest_date": date_str,
        "price_at_decision": price_data.get("price_at_decision", entry_price),
        "price_next_day": price_data.get("price_next_day"),
        "price_fetch_date": price_data.get("price_fetch_date"),
        "decision": decision,
        "confidence": confidence,
        "reasoning_snippet": reasoning[:200],
        "outcome": outcome_data["outcome"],
        "outcome_pct": outcome_data["outcome_pct"],
    }

    with open(BACKTEST_LOG, "a") as f:
        f.write(json.dumps(result_record) + "\n")

    status = f"{outcome_data['outcome']}" if outcome_data["outcome"] != "N/A" else "N/A"
    logger.info(f"Backtest {date_str}: {decision} ({confidence}%) | outcome: {status}")
    return result_record


def generate_summary():
    """Generate summary statistics from backtest results."""
    if not os.path.exists(BACKTEST_LOG):
        print("No backtest runs yet.")
        return

    with open(BACKTEST_LOG) as f:
        runs = [json.loads(l) for l in f if l.strip()]

    if not runs:
        print("No backtest runs yet.")
        return

    total = len(runs)
    actionable = [r for r in runs if r.get("decision") in ("BUY", "SELL")]
    wins = [r for r in runs if r.get("outcome") == "WIN"]
    losses = [r for r in runs if r.get("outcome") == "LOSS"]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (
        win_count / len(actionable) if actionable and len(actionable) > 0 else 0.0
    )

    avg_win_pct = (
        sum(r["outcome_pct"] for r in wins if r.get("outcome_pct")) / len(wins)
        if wins
        else 0.0
    )
    avg_loss_pct = (
        sum(r["outcome_pct"] for r in losses if r.get("outcome_pct")) / len(losses)
        if losses
        else 0.0
    )

    loss_rate = 1 - win_rate
    expectancy = (
        (win_rate * avg_win_pct) - (loss_rate * avg_loss_pct)
        if (win_rate + loss_rate) > 0
        else 0.0
    )

    wins_with_conf = [r for r in wins if r.get("confidence")]
    losses_with_conf = [r for r in losses if r.get("confidence")]

    avg_conf_wins = (
        sum(r["confidence"] for r in wins_with_conf) / len(wins_with_conf)
        if wins_with_conf
        else 0.0
    )
    avg_conf_losses = (
        sum(r["confidence"] for r in losses_with_conf) / len(losses_with_conf)
        if losses_with_conf
        else 0.0
    )

    confidence_predictive = avg_conf_wins > avg_conf_losses + 5

    dates = [r.get("backtest_date") for r in runs if r.get("backtest_date")]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"

    ready_for_saas = win_rate >= 0.62 and expectancy > 0

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_backtests": total,
        "actionable_signals": len(actionable),
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 4),
        "avg_win_pct": round(avg_win_pct, 3),
        "avg_loss_pct": round(avg_loss_pct, 3),
        "expectancy_per_trade": round(expectancy, 3),
        "avg_confidence_wins": round(avg_conf_wins, 1),
        "avg_confidence_losses": round(avg_conf_losses, 1),
        "confidence_predictive": confidence_predictive,
        "date_range": date_range,
        "ready_for_saas": ready_for_saas,
    }

    with open(BACKTEST_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'=' * 50}")
    print(f"BACKTEST SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total backtests: {total}")
    print(f"Actionable signals: {len(actionable)}")
    print(f"Wins: {win_count}, Losses: {loss_count}")
    print(f"Win rate: {win_rate * 100:.1f}%")
    print(f"Expectancy per trade: {expectancy:.2f}%")
    print(f"Ready for SaaS: {ready_for_saas}")
    print(f"{'=' * 50}\n")


def print_summary():
    """Legacy function - redirects to generate_summary."""
    generate_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limitless AI Backtester")
    parser.add_argument("--date", type=str, help="Single date to backtest (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=0, help="Backtest last N days")
    parser.add_argument(
        "--batch", type=int, default=0, help="Run N backtests over past 90 days"
    )
    parser.add_argument(
        "--batch-250",
        dest="batch_250",
        action="store_true",
        help="Run 250 random dates from past 18 months",
    )
    parser.add_argument(
        "--fast", action="store_true", help="Fast/cheap mode: debate_rounds=1"
    )
    parser.add_argument("--summary", action="store_true", help="Print accuracy summary")
    parser.add_argument(
        "--estimate-only",
        dest="estimate_only",
        action="store_true",
        help="Print estimated cost and exit without running",
    )
    args = parser.parse_args()
    args_fast = args.fast
    args_batch_250 = args.batch_250

    if args.estimate_only:
        import random as _rand
        if args.batch_250:
            _today = datetime.now(timezone.utc)
            _cutoff = _today - timedelta(days=7)
            _start = _today - timedelta(days=547)
            _all = []
            _cur = _cutoff
            while _cur > _start:
                _all.append(_cur.strftime("%Y-%m-%d"))
                _cur -= timedelta(days=1)
            if os.path.exists(BACKTEST_LOG):
                with open(BACKTEST_LOG) as _f:
                    _existing = {
                        __j.get("backtest_date")
                        for _l in _f
                        if _l.strip()
                        for __j in [__import__("json").loads(_l)]
                        if __j.get("backtest_date")
                    }
                _all = [d for d in _all if d not in _existing]
            _n = min(250, len(_all))
        elif args.batch:
            _n = args.batch
        elif args.days:
            _n = args.days
        else:
            _n = 1
        _cost = _n * 0.003
        print(f"ESTIMATED COST: ${_cost:.2f} for {_n} runs.")
        sys.exit(0)

    if args.summary:
        generate_summary()
        sys.exit(0)

    dates_to_run = []

    if args.batch_250:
        import random

        today = datetime.now(timezone.utc)
        cutoff_date = today - timedelta(days=7)
        start_date = today - timedelta(days=547)

        all_dates = []
        current = cutoff_date
        while current > start_date:
            all_dates.append(current.strftime("%Y-%m-%d"))
            current -= timedelta(days=1)

        if os.path.exists(BACKTEST_LOG):
            with open(BACKTEST_LOG) as f:
                existing_dates = {
                    json.loads(l).get("backtest_date")
                    for l in f
                    if l.strip() and json.loads(l).get("backtest_date")
                }
            all_dates = [d for d in all_dates if d not in existing_dates]

        dates_to_run = random.sample(all_dates, min(250, len(all_dates)))
        dates_to_run.sort()

        cost = len(dates_to_run) * 0.003
        print(
            f"ESTIMATED COST: ${cost:.2f} for {len(dates_to_run)} runs. Continue? (y/n)"
        )
        response = input("> ").strip().lower()
        if response != "y":
            print("Aborted.")
            sys.exit(0)

        args_fast = True
    elif args.date:
        dates_to_run = [args.date]
    elif args.days:
        today = datetime.now(timezone.utc)
        for i in range(args.days, 0, -1):
            d = today - timedelta(days=i)
            dates_to_run.append(d.strftime("%Y-%m-%d"))
    elif args.batch:
        import random

        today = datetime.now(timezone.utc)
        all_dates = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 91)
        ]
        dates_to_run = random.sample(all_dates, min(args.batch, len(all_dates)))
        dates_to_run.sort()
    else:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        dates_to_run = [yesterday]

    logger.info(f"Running {len(dates_to_run)} backtest(s)...")
    results = []
    for i, date in enumerate(dates_to_run):
        logger.info(f"Progress: {i + 1}/{len(dates_to_run)}")
        r = run_single_backtest(date)
        if r:
            results.append(r)
        time.sleep(3)

    logger.info(f"Completed {len(results)} backtests")
    generate_summary()
