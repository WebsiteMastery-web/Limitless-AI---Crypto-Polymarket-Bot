"""
Limitless AI — Telegram Notifier
Sends trade signal alerts to Sam's Telegram via Limitless AI bot.
Supports both legacy OpenClaw bot and new Limitless AI Signals bot.
"""
import os, requests
from datetime import datetime
from loguru import logger

TELEGRAM_BOT_TOKEN_LIMITLESS = os.getenv("TELEGRAM_BOT_TOKEN_LIMITLESS")
TELEGRAM_CHAT_ID_LIMITLESS = os.getenv("TELEGRAM_CHAT_ID_LIMITLESS")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8022194851:AAEvMKbyv0lHiTutM-GnzbIiZqIZyQXcoU8")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8694352076")


def _send_limitless(message: str) -> bool:
    """Send a message via the Limitless AI bot. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN_LIMITLESS or not TELEGRAM_CHAT_ID_LIMITLESS:
        logger.warning("Limitless AI Telegram credentials not set. Set TELEGRAM_BOT_TOKEN_LIMITLESS and TELEGRAM_CHAT_ID_LIMITLESS in .env")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_LIMITLESS}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID_LIMITLESS,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            logger.info("Limitless AI Telegram notification sent.")
            return True
        else:
            logger.warning(f"Limitless AI Telegram notification failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"Limitless AI Telegram notification error: {e}")
        return False


def send_telegram(message: str) -> bool:
    """Send a message to Sam's Telegram via legacy OpenClaw bot. Returns True on success."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram notification sent.")
            return True
        else:
            logger.warning(f"Telegram notification failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"Telegram notification error: {e}")
        return False


def send_buy_signal(price, confidence, reasoning, regime, mirofish_label):
    """Sends rich BUY alert with full context"""
    if not TELEGRAM_BOT_TOKEN_LIMITLESS:
        logger.warning("TELEGRAM_BOT_TOKEN_LIMITLESS not set - cannot send BUY signal")
        return False
    message = (
        "🟢 <b>LIMITLESS AI — BUY SIGNAL</b>\n\n"
        f"💰 <b>BTC Price:</b> \n"
        f"📊 <b>Confidence:</b> {confidence}%\n"
        f"🌍 <b>Regime:</b> {regime}\n"
        f"🐟 <b>MiroFish:</b> {mirofish_label}\n\n"
        f"<b>Reasoning:</b>\n{reasoning[:400]}"
    )
    return _send_limitless(message)


def send_sell_signal(price, confidence, reasoning, regime, mirofish_label):
    """Sends rich SELL alert"""
    if not TELEGRAM_BOT_TOKEN_LIMITLESS:
        logger.warning("TELEGRAM_BOT_TOKEN_LIMITLESS not set - cannot send SELL signal")
        return False
    message = (
        "🔴 <b>LIMITLESS AI — SELL SIGNAL</b>\n\n"
        f"💰 <b>BTC Price:</b> \n"
        f"📊 <b>Confidence:</b> {confidence}%\n"
        f"🌍 <b>Regime:</b> {regime}\n"
        f"🐟 <b>MiroFish:</b> {mirofish_label}\n\n"
        f"<b>Reasoning:</b>\n{reasoning[:400]}"
    )
    return _send_limitless(message)


def send_hold_summary(price, confidence, runs_today):
    """Sends daily HOLD summary once per day"""
    if not TELEGRAM_BOT_TOKEN_LIMITLESS:
        logger.warning("TELEGRAM_BOT_TOKEN_LIMITLESS not set - cannot send HOLD summary")
        return False
    message = (
        "⏸️ <b>LIMITLESS AI — HOLD SUMMARY</b>\n\n"
        f"💰 <b>BTC Price:</b> \n"
        f"📊 <b>Confidence:</b> {confidence}%\n"
        f"🔄 <b>Runs Today:</b> {runs_today}\n\n"
        "<i>No buy/sell signal triggered. Holding current position.</i>"
    )
    return _send_limitless(message)


def test_connection():
    """Sends test message — call this to verify setup. Returns True if successful."""
    if not TELEGRAM_BOT_TOKEN_LIMITLESS or not TELEGRAM_CHAT_ID_LIMITLESS:
        logger.warning("TELEGRAM_BOT_TOKEN_LIMITLESS or TELEGRAM_CHAT_ID_LIMITLESS not set")
        return False
    message = "✅ <b>Limitless AI Signals Bot Connected!</b>\n\nTrading alerts will be sent here."
    return _send_limitless(message)


def notify_cron_pending(symbol, direction, limit_price, stop_loss_price,
                        quantity, confidence_score, mirofish_output, trade_id):
    """Alert Sam when a BUY/SELL signal fires during a cron run."""
    mf_str = ""
    if mirofish_output:
        mf_label = mirofish_output.get("label", "N/A")
        mf_score = mirofish_output.get("sentiment_score", "N/A")
        mf_agents = mirofish_output.get("agent_count", "N/A")
        mf_str = f"\n🐟 <b>MiroFish:</b> {mf_label} ({mf_score}) — {mf_agents} agents"

    msg = (
        f"🚨 <b>LIMITLESS AI — SIGNAL DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Asset:</b> {symbol}\n"
        f"{'🟢' if direction.upper() == 'BUY' else '🔴'} <b>Signal:</b> {direction.upper()}\n"
        f"💰 <b>Entry Price:</b> \n"
        f"🛑 <b>Stop-Loss:</b> \n"
        f"📦 <b>Quantity:</b> {quantity}\n"
        f"🎯 <b>Confidence:</b> {confidence_score}/100"
        f"{mf_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Trade logged as <b>CRON_PENDING</b> — no order placed.\n"
        f"▶️ Run pipeline manually to confirm or reject:\n"
        f"<code>cd /root/limitless-ai && source TradingAgents/venv/bin/activate && python run_paper_trade.py</code>\n"
        f"🆔 Trade ID: <code>{trade_id}</code>"
    )
    return send_telegram(msg)


def notify_hold(symbol, price, confidence, mirofish_label=None):
    """Periodic HOLD summary — send every 6th cron run to avoid spam."""
    mf_str = f" | MiroFish: {mirofish_label}" if mirofish_label else ""
    msg = (
        f"✅ <b>LIMITLESS AI — HOLD</b>\n"
        f"{symbol} @  | Confidence: {confidence}/100{mf_str}"
    )
    return send_telegram(msg)
