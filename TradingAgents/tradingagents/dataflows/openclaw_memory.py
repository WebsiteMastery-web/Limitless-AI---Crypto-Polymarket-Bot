import os, json
from datetime import datetime
from loguru import logger

OPENCLAW_WORKSPACE = '/root/.openclaw/workspace/limitless-ai'
os.makedirs(OPENCLAW_WORKSPACE, exist_ok=True)


def log_trade_to_openclaw(trade_record: dict) -> bool:
    """
    Write a trade record to the OpenClaw workspace as a markdown file.
    OpenClaw indexes these files automatically, making every trade decision
    searchable via RAG. This is the compounding moat — the agent learns from
    every trade over time.
    """
    try:
        trade_id = trade_record.get('trade_id', 'UNKNOWN')
        timestamp = trade_record.get('timestamp', datetime.utcnow().isoformat())
        asset = trade_record.get('asset', 'N/A')
        direction = trade_record.get('direction', 'N/A')
        entry_price = trade_record.get('entry_price', 'N/A')
        stop_loss = trade_record.get('stop_loss', 'N/A')
        confidence = trade_record.get('confidence_score', 'N/A')
        trigger_layer = trade_record.get('trigger_layer', 'N/A')
        reasoning = trade_record.get('reasoning_chain', 'N/A')
        status = trade_record.get('status', 'N/A')
        outcome = trade_record.get('outcome_pct', None)
        order_id = trade_record.get('order_id', 'N/A')

        # Format as markdown for OpenClaw indexing
        content = f'# Limitless AI Trade #{trade_id}\n\n'
        content += f'**Date:** {timestamp[:10]}  \n'
        content += f'**Asset:** {asset}  \n'
        content += f'**Direction:** {direction}  \n'
        content += f'**Entry Price:** {entry_price}  \n'
        content += f'**Stop-Loss:** {stop_loss}  \n'
        content += f'**Confidence Score:** {confidence}/100  \n'
        content += f'**Trigger Layer:** {trigger_layer}  \n'
        content += f'**Status:** {status}  \n'
        content += f'**Order ID:** {order_id}  \n'
        if outcome is not None:
            content += f'**Outcome:** {outcome}%  \n'
        content += f'\n## Reasoning Chain\n\n{reasoning}\n'
        if trade_record.get('mirofish_output'):
            mf = trade_record['mirofish_output']
            content += f'\n## MiroFish Sentiment Output\n\n'
            content += f'Sentiment: {mf.get("sentiment_score", "N/A")}  \n'
            content += f'Agents: {mf.get("agent_count", "N/A")}  \n'
            content += f'Duration: {mf.get("duration", "N/A")}  \n'

        # Write to OpenClaw workspace
        filename = f'trade_{trade_id}_{asset.replace("/", "")}_{timestamp[:10]}.md'
        filepath = os.path.join(OPENCLAW_WORKSPACE, filename)
        with open(filepath, 'w') as f:
            f.write(content)

        logger.info(f'Trade {trade_id} logged to OpenClaw workspace: {filename}')
        return True

    except Exception as e:
        logger.warning(f'OpenClaw memory write failed for trade {trade_record.get("trade_id")}: {e}')
        return False


def log_signal_to_openclaw(signal_type: str, content: str, date: str = None) -> bool:
    """
    Log any significant signal to OpenClaw memory for pattern learning.
    Signal types: geopolitical, congressional, polymarket, technical
    """
    try:
        if not date:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        filename = f'signal_{signal_type}_{date}_{datetime.utcnow().strftime("%H%M%S")}.md'
        filepath = os.path.join(OPENCLAW_WORKSPACE, filename)
        header = f'# Limitless AI Signal: {signal_type.upper()}\n\n'
        header += f'**Date:** {date}  \n'
        header += f'**Type:** {signal_type}  \n\n'
        with open(filepath, 'w') as f:
            f.write(header + content)
        logger.info(f'Signal logged to OpenClaw: {filename}')
        return True
    except Exception as e:
        logger.warning(f'OpenClaw signal write failed: {e}')
        return False


def update_trade_outcome(trade_id: str, exit_price: float, outcome_pct: float) -> bool:
    """Update a trade file with the final outcome when position closes."""
    try:
        import glob
        pattern = os.path.join(OPENCLAW_WORKSPACE, f'trade_{trade_id}_*.md')
        files = glob.glob(pattern)
        if not files:
            logger.warning(f'No OpenClaw file found for trade {trade_id}')
            return False
        for filepath in files:
            with open(filepath) as f:
                content = f.read()
            outcome_line = f'**Outcome:** {outcome_pct:.2f}%  \n'
            exit_line = f'**Exit Price:** {exit_price}  \n'
            content = content.replace('**Status:** OPEN', f'**Status:** CLOSED')
            if '**Outcome:**' not in content:
                content += f'\n## Trade Outcome\n\n{exit_line}{outcome_line}'
            with open(filepath, 'w') as f:
                f.write(content)
        logger.info(f'Trade {trade_id} outcome updated in OpenClaw: {outcome_pct:.2f}%')
        return True
    except Exception as e:
        logger.warning(f'OpenClaw outcome update failed: {e}')
        return False


def write_limitless_context() -> None:
    """
    Write the Limitless AI context file to the OpenClaw workspace.
    This gives OpenClaw awareness of the trading system when Sam asks
    questions about Limitless AI through the Telegram interface.
    """
    context = '''# Limitless AI — Trading System Context

This file gives OpenClaw awareness of the Limitless AI paper trading system.

## What Limitless AI Is
An autonomous AI trading agent built on TradingAgents (LangGraph multi-agent framework).
Currently in paper trading validation phase. All trades are paper (fake money, real data).
Uses Alpaca paper trading API with $200,000 virtual balance.

## Signal Intelligence Layers
1. **Tavily News** — Real-time global crypto/macro news via agent-optimized search
2. **SEC EDGAR Congressional Signals** — Form 4 insider/congressional trade filings
3. **Polymarket Crowd-Probability** — Prediction market signals on crypto/macro events
4. **Technical Analysis** — OHLCV patterns, RSI, MACD via yfinance
5. **MiroFish Sentiment** (Week 3) — Local LLM swarm sentiment simulation

## Model Routing
- Claude Haiku: data ingestion and classification agents
- Claude Opus: final Portfolio Manager trade decisions only

## Current Status
- Week 1 complete: pipeline running, paper trades executing
- Week 2 complete: all intelligence layers active
- Primary asset: BTC/USD
- Decision history: multiple HOLD decisions at 65% confidence

## Trade Log Location
All trade logs stored at: /root/limitless-ai/logs/trades/
OpenClaw memory files at: /root/.openclaw/workspace/limitless-ai/
'''
    filepath = os.path.join(OPENCLAW_WORKSPACE, 'LIMITLESS_AI_CONTEXT.md')
    with open(filepath, 'w') as f:
        f.write(context)
    logger.info('Limitless AI context written to OpenClaw workspace')
