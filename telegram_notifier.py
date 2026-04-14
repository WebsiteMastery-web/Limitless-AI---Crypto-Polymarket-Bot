#!/usr/bin/env python3
import os, json, requests
from datetime import datetime
from pathlib import Path
from loguru import logger

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_message(text, parse_mode="HTML"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def send_decision_alert(decision, confidence, price, mirofish=None):
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(decision, "⚪")
    msg = f"{emoji} <b>LIMITLESS AI</b>\n\n"
    msg += f"<b>Decision:</b> {decision}\n"
    msg += f"<b>Confidence:</b> {confidence}%\n"
    msg += f"<b>BTC:</b> ${price:,.2f}\n"
    msg += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M UTC')}\n"
    if mirofish:
        msg += f"<b>MiroFish:</b> {mirofish.get('label', 'N/A')}\n"
    if decision in ["BUY", "SELL"]:
        msg += "\n⚠️ <b>ACTION REQUIRED</b>"
    return send_message(msg)

def send_daily_summary():
    log_path = Path("/root/limitless-ai/logs/pipeline_runs.jsonl")
    if not log_path.exists():
        return send_message("📊 No runs logged.")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    runs = []
    with open(log_path) as f:
        for line in f:
            try:
                run = json.loads(line.strip())
                if run.get("timestamp", "").startswith(today):
                    runs.append(run)
            except: pass
    buys = sum(1 for r in runs if r.get("decision")=="BUY")
    sells = sum(1 for r in runs if r.get("decision")=="SELL")
    holds = sum(1 for r in runs if r.get("decision")=="HOLD")
    msg = f"📊 <b>Daily Summary</b> ({today})\n\n"
    msg += f"Runs: {len(runs)}\n"
    msg += f"🟢 BUY: {buys} | 🔴 SELL: {sells} | 🟡 HOLD: {holds}"
    return send_message(msg)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            send_message("🧪 Limitless AI test OK!")
        elif sys.argv[1] == "daily":
            send_daily_summary()
