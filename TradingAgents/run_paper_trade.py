import sys
import os
import datetime
sys.path.insert(0, "/root/limitless-ai/TradingAgents")
from tradingagents.execution.telegram_notifier import notify_hold, send_telegram
sys.path.insert(0, "/root/limitless-ai/TradingAgents")
from dotenv import load_dotenv
load_dotenv("/root/limitless-ai/TradingAgents/.env")
from loguru import logger
from limitless_config import LIMITLESS_CONFIG
from tradingagents.dataflows.alpaca_feed import get_current_price, get_paper_balance, get_ohlcv
sys.path.insert(0, "/root/limitless-ai")
from risk_manager import get_atr_stop
from tradingagents.execution.alpaca_executor import place_paper_trade
from tradingagents.dataflows.openclaw_memory import log_trade_to_openclaw, log_signal_to_openclaw, write_limitless_context
from tradingagents.dataflows.run_logger import log_pipeline_run, get_mirofish_comparison_stats
from tradingagents.dataflows.mirofish_bridge import get_latest_mirofish_signal, format_mirofish_for_agent
from tradingagents.dataflows.run_logger import log_pipeline_run
from tradingagents.dataflows.mirofish_bridge import get_latest_mirofish_signal, format_mirofish_for_agent
from tradingagents.graph.trading_graph import TradingAgentsGraph

def run_cycle(symbol_yfinance="BTC-USD", symbol_alpaca="BTC/USD"):
    logger.info(f"Starting trade cycle | yfinance={symbol_yfinance} alpaca={symbol_alpaca}")
    current_price = get_current_price(symbol_alpaca)
    logger.info(f"Current {symbol_alpaca} price: {current_price}")
    today = datetime.date.today().strftime("%Y-%m-%d")
    graph = TradingAgentsGraph(config=LIMITLESS_CONFIG)
    logger.info("Running TradingAgents analysis pipeline... (takes 2-5 minutes)")
    result, agent_logs = graph.propagate(symbol_yfinance, today)
    decision = result.get("action") or result.get("trade_type") or "HOLD"
    reasoning = str(result.get("reason") or result.get("reasoning") or result)
    confidence = int(result.get("confidence", 65))
    logger.info(f"Decision: {decision} | Confidence: {confidence}")
    # Always attempt MiroFish — logs whether PC was on or off
    mirofish_result = get_latest_mirofish_signal()
    if mirofish_result:
        mf_text = format_mirofish_for_agent(mirofish_result)
        logger.info(f"MiroFish signal available: {mirofish_result.get('sentiment_label')} ({mirofish_result.get('sentiment_score')})")
    else:
        logger.info("MiroFish: PC off or no simulation run yet — proceeding without it")
    # Log every run to comparison database
    log_pipeline_run(
        asset=yf,
        price=current_price,
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        mirofish_result=mirofish_result,
    )
    if decision.upper() not in ["BUY", "SELL"]:
        logger.info("Decision is HOLD. No order placed.")
        # Send Telegram HOLD summary once per day (on the noon run)
        if cron_mode:
            import datetime as _dt
            _hour = _dt.datetime.utcnow().hour
            if _hour in (11, 12):  # noon UTC cron run
                _mf_label = mirofish_signal.get("label") if mirofish_signal else None
                notify_hold(ap, current_price, decision_data.get("confidence", 65), _mf_label)
        return
    balance = get_paper_balance()
    buying_power = balance["buying_power"]
    trade_usd = buying_power * 0.10
    quantity = round(trade_usd / current_price, 4)
    quantity = max(quantity, 0.001)
    atr_stop_data = get_atr_stop()
    trailing_stop_pct = atr_stop_data["stop_loss_pct"] if atr_stop_data else 3.0
    _stop_mult = trailing_stop_pct / 100
    stop_loss = round(
        current_price * (1 - _stop_mult) if decision.upper() == "BUY" else current_price * (1 + _stop_mult), 2
    )
    logger.info(f"ATR stop: {trailing_stop_pct:.2f}% => stop_loss={stop_loss}")
    order = place_paper_trade(
        symbol=symbol_alpaca,
        direction=decision.upper(),
        quantity=quantity,
        limit_price=round(current_price, 2),
        stop_loss_price=stop_loss,
        reasoning_chain=reasoning,
        confidence_score=confidence,
        trigger_layer="tradingagents_full_pipeline",
        mirofish_output=None,
        trailing_stop_pct=trailing_stop_pct
    )
    if order:
        logger.info(f"Week 1 complete. Order ID: {order.id}")

if __name__ == "__main__":
    _args = [a for a in sys.argv[1:] if not a.startswith("--")]
    yf = _args[0] if len(_args) > 0 else "BTC-USD"
    ap = _args[1] if len(_args) > 1 else "BTC/USD"
    cron_mode = "--cron" in sys.argv
    run_cycle(yf, ap)
