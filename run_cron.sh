#!/bin/bash
set -e
LOG=/root/limitless-ai/logs/cron.log
echo "=== CRON RUN $(date -u) ===" >> $LOG

# Safety 1: Kill any Opus model usage
if grep -i "opus" /root/limitless-ai/TradingAgents/.env 2>/dev/null; then
    echo "FATAL: Opus model detected in .env — aborting to prevent cost explosion" >> $LOG
    exit 1
fi

# Safety 2: Check disk space (abort if < 500MB free)
FREE_MB=$(df /root --output=avail -m | tail -1)
if [ "$FREE_MB" -lt 500 ]; then
    echo "WARNING: Low disk space: ${FREE_MB}MB free" >> $LOG
fi

# Safety 3: Watchdog — restart MiroFish receiver if down
if ! curl -s --max-time 3 http://localhost:9876/health | grep -q "ok"; then
    echo "MiroFish receiver down — restarting..." >> $LOG
    systemctl restart mirofish 2>/dev/null || \
    nohup python /root/limitless-ai/mirofish_receiver.py >> /root/limitless-ai/logs/mirofish_receiver.log 2>&1 &
    sleep 5
    echo "MiroFish restart attempted" >> $LOG
fi

# Safety 4: Watchdog — restart dashboard if down
if ! curl -s --max-time 3 http://localhost:8888/api/health | grep -q "ok"; then
    echo "Dashboard down — restarting..." >> $LOG
    pkill -f dashboard_api 2>/dev/null || true
    sleep 2
    nohup python /root/limitless-ai/dashboard_api.py >> /root/limitless-ai/logs/dashboard.log 2>&1 &
    sleep 3
    echo "Dashboard restart attempted" >> $LOG
fi

# Main pipeline run
echo "Starting pipeline run..." >> $LOG
cd /root/limitless-ai
source TradingAgents/venv/bin/activate
timeout 420 python3 run_paper_trade.py --cron >> $LOG 2>&1
PIPELINE_EXIT=$?

if [ $PIPELINE_EXIT -ne 0 ]; then
    echo "Pipeline exited with code $PIPELINE_EXIT" >> $LOG
fi

# Performance update after every pipeline run
python3 performance_tracker.py >> logs/performance_tracker.log 2>&1

echo "=== CRON DONE $(date -u) ===" >> $LOG
