#!/bin/bash
cd /root/limitless-ai

# 6 dates spaced ~5 days apart over last 30 days
DATES=(2026-03-17 2026-03-22 2026-03-27 2026-04-01 2026-04-07 2026-04-11)

echo "=== Launching 6 PARALLEL backtests at $(date -u) ==="

PIDS=()
for DATE in "${DATES[@]}"; do
  echo "Starting $DATE..."
  python3 run_backtest.py --date "$DATE" --fast > /root/limitless-ai/logs/bt_${DATE}.log 2>&1 &
  PIDS+=($!)
done

echo "All 6 launched. PIDs: ${PIDS[@]}"
echo "Waiting for all to finish..."

COMPLETED=0
for i in "${!PIDS[@]}"; do
  wait ${PIDS[$i]}
  EC=$?
  DATE="${DATES[$i]}"
  if [ $EC -eq 0 ]; then
    COMPLETED=$((COMPLETED+1))
    echo "DONE: $DATE (exit $EC) [$COMPLETED/${#DATES[@]}]"
  else
    echo "FAIL: $DATE (exit $EC)"
  fi
done

echo ""
echo "=== $COMPLETED/${#DATES[@]} completed at $(date -u) ==="
python3 run_backtest.py --summary
