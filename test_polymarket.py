#!/usr/bin/env python3
"""
Test script for Polymarket Executor.
Always runs in dry-run mode for safety.
"""

import sys
import os
from pathlib import Path

# Add to path
sys.path.insert(0, "/root/limitless-ai")

from polymarket_executor import (
    scan_markets,
    execute_polymarket_bets,
    get_position_summary,
    resolve_expired_positions,
)


def main():
    print("=" * 60)
    print("POLYMARKET EXECUTOR TEST")
    print("=" * 60)
    print()

    # Test 1: API connectivity
    print(">>> Test 1: API Connectivity")
    try:
        import requests

        r = requests.get(
            "https://gamma-api.polymarket.com/markets?active=true&limit=1", timeout=10
        )
        if r.status_code == 200:
            print("  ✅ Gamma API responding")
        else:
            print(f"  ❌ Gamma API returned {r.status_code}")
            return
    except Exception as e:
        print(f"  ❌ API error: {e}")
        return

    # Test 2: Import test
    print("\n>>> Test 2: Import Test")
    try:
        from polymarket_executor import (
            scan_markets,
            execute_polymarket_bets,
            get_position_summary,
        )

        print("  ✅ All functions imported successfully")
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        return

    # Test 3: Market scan
    print("\n>>> Test 3: Market Scan")
    markets = scan_markets(min_volume_usd=10000, max_markets=10)
    print(f"  Found {len(markets)} relevant markets")
    if markets:
        print("\n  Top 5 opportunities:")
        for i, m in enumerate(markets[:5], 1):
            print(f"    {i}. {m['question'][:60]}")
            print(
                f"       P(YES): {m['probability_yes']:.1%} | Vol: ${m['volume_24h']:,.0f}"
            )
    else:
        print("  ⚠️  No markets found (might be due to API rate limits)")

    # Test 4: Edge calculation test
    print("\n>>> Test 4: Edge Calculation")
    from polymarket_executor import calculate_edge, calculate_stake

    test_cases = [
        (0.40, 0.75, "BUY"),  # Bullish signal on low prob market
        (0.70, 0.80, "SELL"),  # Bearish signal on high prob market
        (0.50, 0.60, "BUY"),  # Weak signal
    ]

    for mkt_prob, conf, decision in test_cases:
        should_bet, side, edge, sys_prob = calculate_edge(mkt_prob, conf, decision)
        stake = calculate_stake(edge) if should_bet else 0
        print(f"  Market {mkt_prob:.0%} + {decision} @ {conf:.0%}: ", end="")
        if should_bet:
            print(f"BET {side} edge={edge:.1%} stake=${stake:.2f}")
        else:
            print(f"skip (edge={edge:.1%} < 8%)")

    # Test 5: Dry-run execution
    print("\n>>> Test 5: Dry-Run Execution")
    print("  Simulating BUY signal @ 75% confidence with 4 layers...")
    result = execute_polymarket_bets("BUY", 0.75, 4, 100.0, dry_run=True)
    print(f"  Opened {len(result)} position(s) in dry-run mode")

    # Test 6: Position summary
    print("\n>>> Test 6: Position Summary")
    summary = get_position_summary()
    print(f"  Total positions: {summary['total_positions']}")
    print(
        f"  Open: {summary['open_positions']} | Resolved: {summary['resolved_positions']}"
    )
    print(f"  Total staked: ${summary['total_staked']:.2f}")
    print(f"  Total PnL: ${summary['total_pnl']:.2f}")
    print(f"  Win rate: {summary['win_rate']:.1%}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
