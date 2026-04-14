#!/usr/bin/env python3
"""Script to update summary calculation and add batch-250 flag"""

import re

# Read the file
with open("/root/limitless-ai/run_backtest.py", "r") as f:
    content = f.read()

# Replace the calculate_summary function
old_summary = r"""def calculate_summary\(stats: Dict\[str, Any\], total_runs: int\) -> Dict\[str, Any\]:
    \"\"\"Calculate summary statistics.\"\"\"

    win_rate = \(\(
        stats\["wins"\] / stats\["evaluated"\] \* 100\) if stats\["evaluated"\] > 0 else 0.0
    \)
    
    # Calculate directional accuracy for HOLD decisions
    hold_evaluations = stats\["correct_holds"\] \+ stats\["missed_signals"\]
    directional_accuracy = \(\(
        stats\["correct_holds"\] / hold_evaluations \* 100\) if hold_evaluations > 0 else 0.0
    \)

    avg_confidence_wins = \(\(
        sum\(stats\["confidence_wins"\]\) / len\(stats\["confidence_wins"\]\)
        if stats\["confidence_wins"\]
        else 0.0
    \)
    avg_confidence_losses = \(\(
        sum\(stats\["confidence_losses"\]\) / len\(stats\["confidence_losses"\]\)
        if stats\["confidence_losses"\]
        else 0.0
    \)
    avg_pct_change_wins = \(\(
        sum\(stats\["pct_change_wins"\]\) / len\(stats\["pct_change_wins"\]\)
        if stats\["pct_change_wins"\]
        else 0.0
    \)
    avg_pct_change_losses = \(\(
        sum\(stats\["pct_change_losses"\]\) / len\(stats\["pct_change_losses"\]\)
        if stats\["pct_change_losses"\]
        else 0.0
    \)

    return \{
        "total_runs": total_runs,
        "buy_signals": stats\["buy_signals"\],
        "sell_signals": stats\["sell_signals"\],
        "hold_signals": stats\["hold_signals"\],
        "evaluated": stats\["evaluated"\],
        "wins": stats\["wins"\],
        "losses": stats\["losses"\],
        "win_rate_pct": round\(win_rate, 1\),
        "correct_holds": stats\["correct_holds"\],
        "missed_signals": stats\["missed_signals"\],
        "directional_accuracy_pct": round\(directional_accuracy, 1\),
        "price_unavailable": stats\["price_unavailable"\],
        "avg_confidence_wins": round\(avg_confidence_wins, 1\),
        "avg_confidence_losses": round\(avg_confidence_losses, 1\),
        "avg_pct_change_wins": round\(avg_pct_change_wins, 2\),
        "avg_pct_change_losses": round\(avg_pct_change_losses, 2\),
        "polymarket_accuracy_pct": None,
    \}"""

new_summary = """def calculate_summary(stats: Dict[str, Any], total_runs: int, date_range: str = "") -> Dict[str, Any]:
    \"\"\"Calculate summary statistics with SAAS-ready metrics.\"\"\"

    actionable = stats["actionable_signals"]
    wins = stats["wins"]
    losses = stats["losses"]
    
    win_rate = (wins / actionable * 100) if actionable > 0 else 0.0
    loss_rate = 100 - win_rate
    
    avg_confidence_wins = (
        sum(stats["confidence_wins"]) / len(stats["confidence_wins"])
        if stats["confidence_wins"]
        else 0.0
    )
    avg_confidence_losses = (
        sum(stats["confidence_losses"]) / len(stats["confidence_losses"])
        if stats["confidence_losses"]
        else 0.0
    )
    avg_win_pct = (
        sum(stats["pct_change_wins"]) / len(stats["pct_change_wins"])
        if stats["pct_change_wins"]
        else 0.0
    )
    avg_loss_pct = (
        sum(stats["pct_change_losses"]) / len(stats["pct_change_losses"])
        if stats["pct_change_losses"]
        else 0.0
    )
    
    # Expectancy per trade = (win_rate * avg_win) - (loss_rate * avg_loss)
    # Note: avg_loss_pct is negative, so we subtract it
    expectancy_per_trade = (win_rate / 100 * avg_win_pct) - (loss_rate / 100 * abs(avg_loss_pct))
    
    # Confidence predictive: wins have higher confidence than losses + 5%
    confidence_predictive = avg_confidence_wins > avg_confidence_losses + 5
    
    # Ready for SAAS: win_rate >= 62% AND expectancy > 0
    ready_for_saas = win_rate >= 62 and expectancy_per_trade > 0

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_backtests": total_runs,
        "actionable_signals": actionable,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "avg_win_pct": round(avg_win_pct, 2),
        "avg_loss_pct": round(avg_loss_pct, 2),
        "expectancy_per_trade": round(expectancy_per_trade, 2),
        "avg_confidence_wins": round(avg_confidence_wins, 1),
        "avg_confidence_losses": round(avg_confidence_losses, 1),
        "confidence_predictive": confidence_predictive,
        "date_range": date_range,
        "ready_for_saas": ready_for_saas,
    }"""

content = re.sub(old_summary, new_summary, content)

# Update the print_and_save_summary function to match new format
old_print = r"""def print_and_save_summary\(summary: Dict\[str, Any\]\):
    \"\"\"Print and save summary to file.\"\"\"

    # Print to console
    logger.info\(f\"\\n\{'=' \* 60\}\"\)
    logger.info\(f\"BACKTEST SUMMARY\"\)
    logger.info\(f\"\{'=' \* 60\}\"\)
    logger.info\(f\"Total runs: \{summary\['total_runs'\]\}\"\)
    logger.info\(f\"Buy signals: \{summary\['buy_signals'\]\}\"\)
    logger.info\(f\"Sell signals: \{summary\['sell_signals'\]\}\"\)
    logger.info\(f\"Hold signals: \{summary\['hold_signals'\]\}\"\)
    logger.info\(f\"Evaluated \(non-HOLD\): \{summary\['evaluated'\]\}\"\)
    logger.info\(f\"Wins: \{summary\['wins'\]\}\"\)
    logger.info\(f\"Losses: \{summary\['losses'\]\}\"\)
    logger.info\(f\"Win rate: \{summary\['win_rate_pct'\]\.1f\}%\"\)
    logger.info\(f\"Correct HOLDs: \{summary\.get\('correct_holds', 0\)\}\"\)
    logger.info\(f\"Missed signals: \{summary\.get\('missed_signals', 0\)\}\"\)
    logger.info\(f\"Directional accuracy: \{summary\.get\('directional_accuracy_pct', 0\)\.1f\}%\"\)
    logger.info\(f\"Price unavailable: \{summary\.get\('price_unavailable', 0\)\}\"\)
    logger.info\(f\"Avg confidence \(wins\): \{summary\['avg_confidence_wins'\]\.1f\}\"\)
    logger.info\(f\"Avg confidence \(losses\): \{summary\['avg_confidence_losses'\]\.1f\}\"\)
    logger.info\(f\"Avg % change \(wins\): \{summary\['avg_pct_change_wins'\]\:+\.2f\}%\"\)
    logger.info\(f\"Avg % change \(losses\): \{summary\['avg_pct_change_losses'\]\:+\.2f\}%\"\)

    if summary\[\"polymarket_accuracy_pct\"\] is not None:
        logger.info\(f\"Polymarket accuracy: \{summary\['polymarket_accuracy_pct'\]\.1f\}%\"\)

    # Save to file
    with open\(SUMMARY_FILE, \"w\"\) as f:
        json\.dump\(summary, f, indent=2\)

    logger\.info\(f\"\\nSummary saved to: \{SUMMARY_FILE\}\"\)"""

new_print = """def print_and_save_summary(summary: Dict[str, Any]):
    \"\"\"Print and save summary to file.\"\"\"

    # Print to console
    logger.info(f\"\\n{'=' * 60}\")
    logger.info(f\"BACKTEST SUMMARY\")
    logger.info(f\"{'=' * 60}\")
    logger.info(f\"Generated at: {summary.get('generated_at', 'N/A')}\")
    logger.info(f\"Date range: {summary.get('date_range', 'N/A')}\")
    logger.info(f\"Total backtests: {summary.get('total_backtests', 0)}\")
    logger.info(f\"Actionable signals: {summary.get('actionable_signals', 0)}\")
    logger.info(f\"Wins: {summary.get('wins', 0)}\")
    logger.info(f\"Losses: {summary.get('losses', 0)}\")
    logger.info(f\"Win rate: {summary.get('win_rate', 0):.1f}%\")
    logger.info(f\"Avg win %: {summary.get('avg_win_pct', 0):+.2f}%\")
    logger.info(f\"Avg loss %: {summary.get('avg_loss_pct', 0):+.2f}%\")
    logger.info(f\"Expectancy per trade: {summary.get('expectancy_per_trade', 0):+.2f}\")
    logger.info(f\"Avg confidence (wins): {summary.get('avg_confidence_wins', 0):.1f}\")
    logger.info(f\"Avg confidence (losses): {summary.get('avg_confidence_losses', 0):.1f}\")
    logger.info(f\"Confidence predictive: {summary.get('confidence_predictive', False)}\")
    logger.info(f\"Ready for SAAS: {summary.get('ready_for_saas', False)}\")

    # Save to file
    with open(SUMMARY_FILE, \"w\") as f:
        json.dump(summary, f, indent=2)

    logger.info(f\"\\nSummary saved to: {SUMMARY_FILE}\")"""

content = re.sub(old_print, new_print, content)

# Write the modified content
with open("/root/limitless-ai/run_backtest.py", "w") as f:
    f.write(content)

print("Third set of replacements done")
