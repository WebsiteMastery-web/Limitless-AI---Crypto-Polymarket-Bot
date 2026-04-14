#!/usr/bin/env python3
"""Script to add --batch-250 flag and function"""

import re

# Read the file
with open("/root/limitless-ai/run_backtest.py", "r") as f:
    content = f.read()

# Add a function for getting dates for batch-250 mode
# Find the get_dates_for_batch_mode function and add the new function after it

batch_250_func = '''

def get_dates_for_batch_250_mode() -> list:
    """
    Generate 250 random dates from past 18 months.
    Excludes:
    - Last 7 days (not enough time for D+1 price)
    - Dates already in backtest_results.jsonl
    """
    import json
    
    now = datetime.now()
    eighteen_months_ago = now - timedelta(days=540)  # 18 months
    seven_days_ago = now - timedelta(days=7)
    
    # Load existing dates from results file
    existing_dates = set()
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        existing_dates.add(record.get("backtest_date", ""))
                    except:
                        pass
        except:
            pass
    
    # Generate all possible dates in the range
    potential_dates = []
    current = eighteen_months_ago
    
    while current < seven_days_ago:
        # Use date only (no time) for batch-250 mode
        dt = current.replace(hour=0, minute=0, second=0, microsecond=0)
        date_str = dt.strftime("%Y-%m-%d")
        
        # Skip if already tested
        if date_str not in existing_dates:
            potential_dates.append(dt)
        
        current += timedelta(days=1)
    
    # Random sample of 250
    if len(potential_dates) >= 250:
        dates = random.sample(potential_dates, 250)
    else:
        dates = potential_dates
    
    dates.sort()
    return dates


def run_batch_250_mode(fast: bool, ticker: str = "BTC-USD") -> Dict[str, Any]:
    """
    Run backtest in --batch-250 mode.
    Tests 250 random dates from past 18 months, excluding last 7 days.
    """
    # Get random dates
    dates = get_dates_for_batch_250_mode()
    num_dates = len(dates)
    
    # Cost estimation
    cost_per_run = 0.003  # DeepSeek + Minimax free tier
    estimated_cost = num_dates * cost_per_run
    
    logger.info(f"Batch-250 mode: {num_dates} random dates from past 18 months")
    logger.info(f"Last 7 days excluded (not enough time for D+1 price)")
    logger.info(f"ESTIMATED COST: ${estimated_cost:.2f} for {num_dates} runs")
    
    # Ask for confirmation
    response = input(f"ESTIMATED COST: ${estimated_cost:.2f} for {num_dates} runs. Continue? (y/n): ")
    if response.lower() != 'y':
        logger.info("Aborted by user")
        return {"buy_signals": 0, "sell_signals": 0, "hold_signals": 0, "actionable_signals": 0, 
                "wins": 0, "losses": 0, "confidence_wins": [], "confidence_losses": [],
                "pct_change_wins": [], "pct_change_losses": []}
    
    logger.info("Starting batch-250 backtest...")
    
    # Apply fast mode config if requested
    if fast:
        try:
            from TradingAgents import limitless_config
            limitless_config.max_debate_rounds = 1
            logger.info("Fast mode: max_debate_rounds set to 1")
        except Exception as e:
            logger.warning(f"Could not apply fast mode config: {e}")

    # Load TradingAgents pipeline
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from limitless_config import LIMITLESS_CONFIG, SELECTED_ANALYSTS

        ta = TradingAgentsGraph(
            debug=False, config=LIMITLESS_CONFIG, selected_analysts=SELECTED_ANALYSTS
        )
        logger.info("TradingAgents pipeline loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load TradingAgents: {e}")
        raise

    stats = {
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
    }
    
    # Track date range
    if dates:
        date_range = f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}"
    else:
        date_range = ""

    for i, decision_dt in enumerate(dates):
        date_str = decision_dt.strftime("%Y-%m-%d")
        time_str = "00:00"  # Always use midnight for batch-250

        logger.info(f"\\n{'=' * 60}")
        logger.info(f"Testing: {date_str} ({i + 1}/{len(dates)})")

        # Get price at decision time (use noon for more reliable data)
        decision_dt_noon = decision_dt.replace(hour=12, minute=0)
        price_at_decision = get_price_at_time(ticker, decision_dt_noon)

        if price_at_decision is None:
            logger.warning(f"Could not fetch price at {decision_dt_noon}, skipping")
            continue

        logger.info(f"Price at decision: ${price_at_decision:,.2f}")

        # Run the LLM pipeline for this date
        try:
            date_str_for_pipeline = decision_dt.strftime("%Y-%m-%d")
            final_state = ta.propagate(ticker, date_str_for_pipeline)

            if isinstance(final_state, (tuple, list)):
                final_state = final_state[0] if final_state else {}

            decision, confidence, reasoning = parse_decision(final_state)
            logger.info(f"Decision: {decision} | Confidence: {confidence}%")

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            continue

        # Get next day price for outcome tracking
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
        )

        # Update stats - count only actionable signals (BUY/SELL) for win rate
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
                stats["pct_change_losses"].append(outcome_pct)

        # Create result record with D+1 outcome tracking
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
        }

        # Write to file immediately
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(result) + "\\n")

        # Rate limit between runs (3 seconds to avoid API rate limits)
        if i < len(dates) - 1:
            wait_time = 3
            logger.info(f"Waiting {wait_time}s...")
            import time
            time.sleep(wait_time)

    # Add date_range to be returned
    stats["date_range"] = date_range
    return stats

'''

# Find where to insert the new function (after get_dates_for_batch_mode)
# We'll insert after the run_polymarket_backtest function starts
insert_point = "async def run_polymarket_backtest():"
content = content.replace(insert_point, batch_250_func + insert_point)

# Now add the --batch-250 argument to the parser
old_args = """    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode: random 30 dates from past year at random 4-hour marks",
    )"""

new_args = """    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode: random 30 dates from past year at random 4-hour marks",
    )
    parser.add_argument(
        "--batch-250",
        action="store_true",
        help="Batch-250 mode: 250 random dates from past 18 months, excludes last 7 days",
    )"""

content = content.replace(old_args, new_args)

# Update the main function to handle --batch-250
old_main_block = """    if args.batch:
        logger.info("Running batch mode (random 30 dates from past year)...")
        stats = run_batch_mode(args.fast, args.ticker)
        total_runs = stats["actionable_signals"]
    elif args.days > 0:"""

new_main_block = """    if args.batch_250:
        logger.info("Running batch-250 mode...")
        stats = run_batch_250_mode(args.fast, args.ticker)
        total_runs = stats.get("actionable_signals", 0)
        date_range = stats.get("date_range", "")
    elif args.batch:
        logger.info("Running batch mode (random 30 dates from past year)...")
        stats = run_batch_mode(args.fast, args.ticker)
        total_runs = stats["actionable_signals"]
        date_range = ""
    elif args.days > 0:"""

content = content.replace(old_main_block, new_main_block)

# Update the summary call to include date_range
old_summary_call = """    # Calculate and print summary
    summary = calculate_summary(stats, total_runs)"""

new_summary_call = """    # Calculate and print summary
    summary = calculate_summary(stats, total_runs, date_range)"""

content = content.replace(old_summary_call, new_summary_call)

# Write the modified content
with open("/root/limitless-ai/run_backtest.py", "w") as f:
    f.write(content)

print("Fourth set of replacements done - batch-250 added")
