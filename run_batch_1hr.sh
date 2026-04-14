#!/bin/bash
cd /root/limitless-ai

# 7 dates spaced ~4 days apart over last 30 days (2026-04-07 already done)
DATES=(
  2026-03-17
  2026-03-21
  2026-03-25
  2026-03-29
  2026-04-02
  2026-04-09
  2026-04-12
)

echo "=== Starting 7 backtests at $(date -u) ==="
COMPLETED=0

for i in "${!DATES[@]}"; do
  DATE="${DATES[$i]}"
  NUM=$((i + 1))
  echo ""
  echo ">>> [$NUM/7] Backtesting $DATE at $(date -u) ..."
  timeout 600 python3 run_backtest.py --date "$DATE" --fast 2>&1
  EXIT_CODE=$?
  if [ $EXIT_CODE -eq 0 ]; then
    COMPLETED=$((COMPLETED + 1))
    echo "<<< [$NUM/7] $DATE completed"
  else
    echo "<<< [$NUM/7] $DATE FAILED (exit $EXIT_CODE)"
  fi
done

echo ""
echo "=== Done. $COMPLETED/7 completed at $(date -u) ==="
python3 run_backtest.py --summary 2>&1
