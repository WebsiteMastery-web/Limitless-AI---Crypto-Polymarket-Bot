#!/usr/bin/env python3
"""
Performance Tracker for Limitless AI
Calculates comprehensive performance metrics from pipeline runs.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

LOGS_DIR = Path("/root/limitless-ai/logs")
PIPELINE_LOG = LOGS_DIR / "pipeline_runs.jsonl"
PERFORMANCE_LOG = LOGS_DIR / "performance.json"


def load_pipeline_runs(days=30):
    runs = []
    cutoff = datetime.utcnow() - timedelta(days=days)
    if not PIPELINE_LOG.exists():
        return runs
    with open(PIPELINE_LOG) as f:
        for line in f:
            try:
                run = json.loads(line.strip())
                ts = datetime.fromisoformat(run["timestamp"].replace("Z", ""))
                if ts >= cutoff:
                    runs.append(run)
            except:
                continue
    return runs


def calculate_performance(lookback_days=30):
    runs = load_pipeline_runs(lookback_days)
    if not runs:
        return {"total_runs": 0, "error": "No runs found"}

    total_runs = len(runs)
    total_buy = sum(1 for r in runs if r.get("decision") == "BUY")
    total_sell = sum(1 for r in runs if r.get("decision") == "SELL")
    total_hold = sum(1 for r in runs if r.get("decision") == "HOLD")

    action_rate = (total_buy + total_sell) / total_runs if total_runs > 0 else 0.0

    confidences = [r.get("confidence", 0) for r in runs]
    avg_confidence_all = sum(confidences) / len(confidences) if confidences else 0.0

    buy_runs = [r for r in runs if r.get("decision") == "BUY"]
    sell_runs = [r for r in runs if r.get("decision") == "SELL"]

    avg_confidence_buy = (
        sum(r.get("confidence", 0) for r in buy_runs) / len(buy_runs)
        if buy_runs
        else 0.0
    )
    avg_confidence_sell = (
        sum(r.get("confidence", 0) for r in sell_runs) / len(sell_runs)
        if sell_runs
        else 0.0
    )

    mirofish_used = sum(1 for r in runs if r.get("mirofish_used", False))
    mirofish_used_pct = (mirofish_used / total_runs * 100) if total_runs > 0 else 0.0

    mirofish_aligned = 0
    mirofish_total = 0
    for r in runs:
        if r.get("mirofish_used"):
            mirofish_total += 1
            mf_label = r.get("mirofish_label", "NEUTRAL")
            decision = r.get("decision", "HOLD")
            if (mf_label == "BULLISH" and decision == "BUY") or (
                mf_label == "BEARISH" and decision == "SELL"
            ):
                mirofish_aligned += 1

    mirofish_alignment_rate = (
        (mirofish_aligned / mirofish_total * 100) if mirofish_total > 0 else 0.0
    )

    short_horizon_acc = calculate_short_horizon_accuracy(runs)
    conf_cal = calculate_confidence_calibration(runs)
    best_combo = calculate_best_signal_combo(runs)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "lookback_days": lookback_days,
        "total_runs": total_runs,
        "decision_stats": {
            "BUY": total_buy,
            "SELL": total_sell,
            "HOLD": total_hold,
            "action_rate": round(action_rate, 4),
        },
        "avg_confidence": round(avg_confidence_all, 2),
        "avg_confidence_buy": round(avg_confidence_buy, 2),
        "avg_confidence_sell": round(avg_confidence_sell, 2),
        "mirofish_stats": {
            "used_pct": round(mirofish_used_pct, 2),
            "alignment_rate": round(mirofish_alignment_rate, 2),
        },
        "short_horizon_accuracy": short_horizon_acc,
        "confidence_calibration": conf_cal,
        "best_signal_combo": best_combo,
    }


def calculate_short_horizon_accuracy(runs):
    try:
        import yfinance as yf
    except ImportError:
        return {
            "evaluated": 0,
            "correct": 0,
            "accuracy_pct": 0.0,
            "error": "yfinance not available",
        }

    sorted_runs = sorted(runs, key=lambda x: x.get("timestamp", ""))
    cutoff_time = datetime.utcnow() - timedelta(hours=4)

    correct = 0
    evaluated = 0

    for run in sorted_runs:
        try:
            run_time = datetime.fromisoformat(run["timestamp"].replace("Z", ""))
            if run_time > cutoff_time:
                continue

            asset = run.get("asset", "BTC-USD")
            if asset.startswith("-"):
                continue
            if "BTC" in asset:
                ticker = "BTC-USD"
            elif "ETH" in asset:
                ticker = "ETH-USD"
            else:
                ticker = asset

            current_price = run.get("price_at_decision", 0)
            if current_price <= 0:
                continue

            try:
                hist = yf.download(ticker, period="1d", interval="1h", progress=False)
                if hist.empty:
                    continue

                future_prices = hist[hist.index > run_time]
                if future_prices.empty:
                    continue

                future_price = future_prices["Close"].iloc[0]
                if future_price <= 0:
                    continue

                price_change = (future_price - current_price) / current_price
                decision = run.get("decision", "HOLD")

                evaluated += 1
                if decision == "BUY" and price_change > 0:
                    correct += 1
                elif decision == "SELL" and price_change < 0:
                    correct += 1
                elif decision == "HOLD" and abs(price_change) < 0.02:
                    correct += 1
            except Exception:
                continue
        except Exception:
            continue

    accuracy_pct = (correct / evaluated * 100) if evaluated > 0 else 0.0
    return {
        "evaluated": evaluated,
        "correct": correct,
        "accuracy_pct": round(accuracy_pct, 2),
    }


def calculate_confidence_calibration(runs):
    high_conf_moves = []
    low_conf_moves = []

    sorted_runs = sorted(runs, key=lambda x: x.get("timestamp", ""))

    for i, run in enumerate(sorted_runs[:-1]):
        confidence = run.get("confidence", 0)
        current_price = run.get("price_at_decision", 0)
        if current_price <= 0:
            continue

        try:
            next_price = sorted_runs[i + 1].get("price_at_decision", 0)
            if next_price <= 0:
                continue
            price_change = abs((next_price - current_price) / current_price)
        except:
            continue

        if confidence >= 80:
            high_conf_moves.append(price_change)
        elif confidence <= 70:
            low_conf_moves.append(price_change)

    high_conf_avg = (
        sum(high_conf_moves) / len(high_conf_moves) * 100 if high_conf_moves else 0.0
    )
    low_conf_avg = (
        sum(low_conf_moves) / len(low_conf_moves) * 100 if low_conf_moves else 0.0
    )

    return {
        "high_conf_avg_move": round(high_conf_avg, 4),
        "low_conf_avg_move": round(low_conf_avg, 4),
        "high_conf_count": len(high_conf_moves),
        "low_conf_count": len(low_conf_moves),
    }


def calculate_best_signal_combo(runs):
    signal_stats = {
        "mirofish_only": {"correct": 0, "total": 0},
        "geo_only": {"correct": 0, "total": 0},
        "polymarket_only": {"correct": 0, "total": 0},
        "mirofish_geo": {"correct": 0, "total": 0},
        "mirofish_polymarket": {"correct": 0, "total": 0},
        "geo_polymarket": {"correct": 0, "total": 0},
        "all_three": {"correct": 0, "total": 0},
    }

    sorted_runs = sorted(runs, key=lambda x: x.get("timestamp", ""))

    for i, run in enumerate(sorted_runs[:-1]):
        current_price = run.get("price_at_decision", 0)
        if current_price <= 0:
            continue

        try:
            next_price = sorted_runs[i + 1].get("price_at_decision", 0)
            if next_price <= 0:
                continue
            price_change = next_price - current_price
            decision = run.get("decision", "HOLD")

            was_correct = False
            if decision == "BUY" and price_change > 0:
                was_correct = True
            elif decision == "SELL" and price_change < 0:
                was_correct = True
            elif decision == "HOLD" and abs(price_change) / current_price < 0.02:
                was_correct = True
        except:
            continue

        mirofish = run.get("mirofish_used", False)
        geo = run.get("tavily_articles", 0) > 0 or run.get("edgar_filings", 0) > 0
        polymarket = run.get("polymarket_markets", 0) > 0

        combo_key = None
        if mirofish and not geo and not polymarket:
            combo_key = "mirofish_only"
        elif geo and not mirofish and not polymarket:
            combo_key = "geo_only"
        elif polymarket and not mirofish and not geo:
            combo_key = "polymarket_only"
        elif mirofish and geo and not polymarket:
            combo_key = "mirofish_geo"
        elif mirofish and polymarket and not geo:
            combo_key = "mirofish_polymarket"
        elif geo and polymarket and not mirofish:
            combo_key = "geo_polymarket"
        elif mirofish and geo and polymarket:
            combo_key = "all_three"

        if combo_key:
            signal_stats[combo_key]["total"] += 1
            if was_correct:
                signal_stats[combo_key]["correct"] += 1

    best_combo = {"name": "none", "accuracy": 0.0}
    for combo, stats in signal_stats.items():
        if stats["total"] >= 2:
            accuracy = (stats["correct"] / stats["total"]) * 100
            if accuracy > best_combo["accuracy"]:
                best_combo = {
                    "name": combo,
                    "accuracy": round(accuracy, 2),
                    "total": stats["total"],
                }

    return best_combo


def main():
    import sys

    full_report = "--full" in sys.argv

    perf = calculate_performance(30)

    with open(PERFORMANCE_LOG, "w") as f:
        json.dump(perf, f, indent=2)

    print(f"Performance report generated: {perf.get('total_runs', 0)} runs analyzed")
    print(
        f"  BUY: {perf.get('decision_stats', {}).get('BUY', 0)}, SELL: {perf.get('decision_stats', {}).get('SELL', 0)}, HOLD: {perf.get('decision_stats', {}).get('HOLD', 0)}"
    )
    print(
        f"  Action rate: {perf.get('decision_stats', {}).get('action_rate', 0) * 100:.1f}%"
    )
    print(
        f"  MiroFish alignment: {perf.get('mirofish_stats', {}).get('alignment_rate', 0):.1f}%"
    )
    print(
        f"  Short-horizon accuracy: {perf.get('short_horizon_accuracy', {}).get('accuracy_pct', 0):.1f}%"
    )
    print(
        f"  Best signal combo: {perf.get('best_signal_combo', {}).get('name', 'none')} ({perf.get('best_signal_combo', {}).get('accuracy', 0):.1f}%)"
    )
    print(f"  Written to: {PERFORMANCE_LOG}")

    if full_report:
        print("\n[--full] Running Elo updates from recent resolved trades...")
        try:
            from agent_elo import update_elos_from_recent
            update_elos_from_recent(lookback_hours=8)
        except Exception as e:
            print(f"[ELO] Update failed: {e}")


if __name__ == "__main__":
    main()
