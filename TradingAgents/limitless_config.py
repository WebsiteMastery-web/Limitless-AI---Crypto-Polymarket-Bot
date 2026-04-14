import os
from dotenv import load_dotenv
load_dotenv('/root/limitless-ai/TradingAgents/.env')

LIMITLESS_CONFIG = {
    'project_dir': '/root/limitless-ai/TradingAgents/tradingagents',
    'llm_provider': 'anthropic',
    'deep_think_llm': os.getenv('TRADINGAGENTS_DEEP_THINK_LLM', 'claude-haiku-4-5-20251001'),
    'quick_think_llm': os.getenv('TRADINGAGENTS_QUICK_THINK_LLM', 'claude-haiku-4-5-20251001'),
    'anthropic_effort': None,
    'max_debate_rounds': 1,
    'max_risk_discuss_rounds': 1,
    'data_vendors': {
        'core_stock_apis': 'yfinance',
        'technical_indicators': 'yfinance',
        'fundamental_data': 'yfinance',
        'news_data': 'tavily',
    },
    'results_dir': '/root/limitless-ai/results',
}

SELECTED_ANALYSTS = ['market', 'social', 'news', 'fundamentals']
