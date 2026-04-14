#!/bin/bash
# Limitless AI — Cron Runner
# Uses full venv python path — no reliance on source/activate in cron shell

VENV_PYTHON="/root/limitless-ai/TradingAgents/venv/bin/python"
RUNNER="/root/limitless-ai/run_paper_trade.py"
LOG_DIR="/root/limitless-ai/logs"
RECEIVER_SCRIPT="/root/limitless-ai/mirofish_receiver.py"

mkdir -p "$LOG_DIR"

# --- Watchdog: restart MiroFish receiver if dead ---
if ! curl -s --max-time 3 http://localhost:9876/health > /dev/null 2>&1; then
    echo "[$(date -u)] MiroFish receiver down — restarting..." >> "$LOG_DIR/cron.log"
    cd /root/limitless-ai && nohup $VENV_PYTHON mirofish_receiver.py >> "$LOG_DIR/mirofish_receiver.log" 2>&1 &
    sleep 3
    if curl -s --max-time 3 http://localhost:9876/health > /dev/null 2>&1; then
        echo "[$(date -u)] MiroFish receiver restarted OK." >> "$LOG_DIR/cron.log"
    else
        echo "[$(date -u)] WARNING: MiroFish receiver failed to restart." >> "$LOG_DIR/cron.log"
    fi
else
    echo "[$(date -u)] MiroFish receiver OK." >> "$LOG_DIR/cron.log"
fi

# --- Run pipeline ---
echo "[$(date -u)] Starting pipeline run..." >> "$LOG_DIR/cron.log"
cd /root/limitless-ai && $VENV_PYTHON "$RUNNER" --cron >> "$LOG_DIR/cron.log" 2>&1
echo "[$(date -u)] Pipeline run complete." >> "$LOG_DIR/cron.log"
