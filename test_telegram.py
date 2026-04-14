"""
Run this to verify Telegram alerts are working.
Usage: python3 test_telegram.py
"""
import sys
import os
from dotenv import load_dotenv
sys.path.insert(0, '/root/limitless-ai/TradingAgents')
load_dotenv('/root/limitless-ai/TradingAgents/.env')
from tradingagents.execution.telegram_notifier import test_connection
result = test_connection()
print("Telegram OK" if result else "Telegram FAILED — check .env for TELEGRAM_BOT_TOKEN_LIMITLESS and TELEGRAM_CHAT_ID_LIMITLESS")
