#!/usr/bin/env python3
"""Script to update run_backtest.py with additional changes"""

import re

# Read the file
with open("/root/limitless-ai/run_backtest.py", "r") as f:
    content = f.read()

# Replace price_4h_later calls with next_day_price
content = content.replace("price_4h_later", "price_next_day")

# Replace determine_outcome calls with determine_outcome_d1
# We need to be careful to only replace the function call signature, not the function definition
# The pattern is: outcome, correct, pct_change = determine_outcome(...)
# We need to change it to: outcome, outcome_pct = determine_outcome_d1(...)

# In run_backtest_mode function - find and replace the outcome calculation block
old_block = """        # Get price 4 hours later
        price_4h = get_price_4h_later(ticker, decision_dt)

        if price_4h is None:
            logger.warning(f"Could not fetch price 4h later, skipping")
            continue

        logger.info(f"Price 4h later: ${price_4h:,.2f}")

        # Determine outcome
        outcome, correct, pct_change = determine_outcome(
            decision, price_at_decision, price_4h
        )

        logger.info(
            f"Outcome: {outcome} | Change: {pct_change:+.2f}% | Correct: {correct}"
        )"""

new_block = """        # Get next day price for outcome tracking
        price_next_day, price_fetch_date = get_next_day_price(ticker, decision_dt)

        if price_next_day is None:
            logger.warning(f"Could not fetch next day price, skipping")
            continue

        logger.info(f"Next day price: ${price_next_day:,.2f} (fetched: {price_fetch_date})")

        # Determine outcome based on D to D+1 price movement
        outcome, outcome_pct = determine_outcome_d1(
            decision, price_at_decision, price_next_day
        )

        logger.info(
            f"Outcome: {outcome} | Change: {outcome_pct:+.2f}%" if outcome_pct else f"Outcome: {outcome}"
        )"""

content = content.replace(old_block, new_block)

# Now update the stats tracking - remove the old complexity and simplify
old_stats_block = """        # Update stats
        decision_upper = decision.upper()
        if decision_upper == "BUY":
            stats["buy_signals"] += 1
        elif decision_upper == "SELL":
            stats["sell_signals"] += 1
        else:
            stats["hold_signals"] += 1

        # Track all outcome types for directional accuracy
        if outcome in ("WIN", "LOSS"):
            stats["evaluated"] += 1

            if outcome == "WIN":
                stats["wins"] += 1
                stats["confidence_wins"].append(confidence)
                stats["pct_change_wins"].append(pct_change)
            else:
                stats["losses"] += 1
                stats["confidence_losses"].append(confidence)
                stats["pct_change_losses"].append(pct_change)
        
        # Track HOLD outcomes directionally
        if outcome == "CORRECT_HOLD":
            stats["correct_holds"] += 1
        elif outcome == "MISSED_BUY":
            stats["missed_signals"] += 1
        elif outcome == "PRICE_UNAVAILABLE":
            stats["price_unavailable"] += 1"""

new_stats_block = """        # Update stats - count only actionable signals (BUY/SELL) for win rate
        decision_upper = decision.upper()
        if decision_upper == "BUY":
            stats["buy_signals"] += 1
            stats["actionable_signals"] += 1
        elif decision_upper == "SELL":
            stats["sell_signals"] += 1
            stats["actionable_signals"] += 1
        else:
            stats["hold_signals"] += 1

        # Track WIN/LOSS outcomes only for actionable signals
        if outcome == "WIN":
            stats["wins"] += 1
            stats["confidence_wins"].append(confidence)
            if outcome_pct is not None:
                stats["pct_change_wins"].append(outcome_pct)
        elif outcome == "LOSS":
            stats["losses"] += 1
            stats["confidence_losses"].append(confidence)
            if outcome_pct is not None:
                stats["pct_change_losses"].append(outcome_pct)"""

content = content.replace(old_stats_block, new_stats_block)

# Update the result record format
old_result = """        # Create result record
        run_id = generate_run_id()
        result = {
            "run_id": run_id,
            "backtest_date": date_str,
            "decision_time": time_str,
            "decision": decision,
            "confidence": confidence,
            "price_at_decision": round(price_at_decision, 2),
            "price_4h_later": round(price_4h, 2),
            "pct_change_4h": round(pct_change, 3),
            "outcome": outcome,
            "correct": correct,
            "reasoning_summary": reasoning,
            "data_sources_used": ["yfinance", "llm_pipeline"],
        }"""

new_result = """        # Create result record with D+1 outcome tracking
        run_id = generate_run_id()
        result = {
            "run_id": run_id,
            "backtest_date": date_str,
            "decision_time": time_str,
            "decision": decision,
            "confidence": confidence,
            "price_at_decision": round(price_at_decision, 2),
            "price_next_day": round(price_next_day, 2),
            "price_fetch_date": price_fetch_date,
            "outcome": outcome,
            "outcome_pct": round(outcome_pct, 3) if outcome_pct is not None else None,
            "reasoning_summary": reasoning,
            "data_sources_used": ["yfinance", "llm_pipeline"],
        }"""

content = content.replace(old_result, new_result)

# Update stats initialization to include actionable_signals
old_init = """    stats = {
        "buy_signals": 0,
        "sell_signals": 0,
        "hold_signals": 0,
        "wins": 0,
        "losses": 0,
        "evaluated": 0,
        "correct_holds": 0,
        "missed_signals": 0,
        "price_unavailable": 0,
        "confidence_wins": [],
        "confidence_losses": [],
        "pct_change_wins": [],
        "pct_change_losses": [],
    }"""

new_init = """    stats = {
        "buy_signals": 0,
        "sell_signals": 0,
        "hold_signals": 0,
        "actionable_signals": 0,
        "wins": 0,
        "losses": 0,
        "confidence_wins": [],
        "confidence_losses": [],
        "pct_change_wins": [],
        "pct_change_losses": [],
    }"""

# This appears twice in the file (once in run_backtest_mode, once in run_batch_mode)
content = content.replace(old_init, new_init)

# Update total_runs calculation
old_total = """        total_runs = (
            stats["buy_signals"] + stats["sell_signals"] + stats["hold_signals"]
        )"""
new_total = """        total_runs = stats["actionable_signals"]"""

content = content.replace(old_total, new_total)

# Write the modified content
with open("/root/limitless-ai/run_backtest.py", "w") as f:
    f.write(content)

print("Second set of replacements done")
