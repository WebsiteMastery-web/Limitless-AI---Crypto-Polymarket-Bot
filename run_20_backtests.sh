#!/bin/bash
cd /root/limitless-ai

# 20 dates spaced ~1.5 days apart, last 30 days (2026-03-15 to 2026-04-13)
# Skipping 2026-04-10 (already ran), favoring weekdays for better data
DATES=(
  2026-03-15
  2026-03-17
  2026-03-18
  2026-03-20
  2026-03-21
  2026-03-24
  2026-03-25
  2026-03-27
  2026-03-28
  2026-03-31
  2026-04-01
  2026-04-02
  2026-04-03
  2026-04-04
  2026-04-05
  2026-04-07
  2026-04-08
  2026-04-09
  2026-04-11
  2026-04-12
)

echo "=== Starting 20 backtests at $(date -u) ==="
COMPLETED=0
FAILED=0

for i in "${!DATES[@]}"; do
  DATE="${DATES[$i]}"
  NUM=$((i + 1))
  echo ""
  echo ">>> [$NUM/20] Backtesting $DATE at $(date -u) ..."
  timeout 900 python3 run_backtest.py --date "$DATE" --fast 2>&1
  EXIT_CODE=$?
  if [ $EXIT_CODE -eq 0 ]; then
    COMPLETED=$((COMPLETED + 1))
    echo "<<< [$NUM/20] $DATE completed"
  else
    FAILED=$((FAILED + 1))
    echo "<<< [$NUM/20] $DATE FAILED (exit $EXIT_CODE)"
  fi
done

echo ""
echo "=== All runs done. $COMPLETED completed, $FAILED failed at $(date -u) ==="
echo ""
echo ">>> Generating final summary..."
python3 run_backtest.py --summary 2>&1
