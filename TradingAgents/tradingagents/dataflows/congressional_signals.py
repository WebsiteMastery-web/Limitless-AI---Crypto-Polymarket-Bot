import os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger

load_dotenv('/root/limitless-ai/TradingAgents/.env')

HEADERS = {
    'User-Agent': 'LimitlessAI/1.0 research@limitlessai.com',
    'Accept': 'application/json'
}


def get_congressional_trades(lookback_days: int = 30, limit: int = 10) -> str:
    """Fetch recent insider/congressional trade filings from SEC EDGAR Form 4."""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        url = 'https://efts.sec.gov/LATEST/search-index'
        params = {'q': '"purchase" OR "sale"', 'forms': '4',
                  'dateRange': 'custom', 'startdt': start_date, 'enddt': end_date}
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        total = data.get('hits', {}).get('total', {}).get('value', 0)
        hits = data.get('hits', {}).get('hits', [])
        if not hits:
            return f'No insider/congressional filings for last {lookback_days} days.'
        output = f'SEC EDGAR Insider/Congressional Trade Filings ({start_date} to {end_date}):\n'
        output += f'Total filings in period: {total}\n\n'
        for i, hit in enumerate(hits[:limit], 1):
            src = hit.get('_source', {})
            names = src.get('display_names', [])
            name_str = ', '.join(names[:2]) if names else 'N/A'
            output += f'{i}. Filed: {src.get("file_date", "N/A")} | Form: {src.get("form", "N/A")}\n'
            output += f'   Filer: {name_str}\n'
            output += f'   Period: {src.get("period_ending", "N/A")} | Location: {src.get("biz_locations", ["N/A"])}\n\n'
        logger.info(f'Congressional/insider trades fetched: {len(hits)} from EDGAR (total: {total})')
        return output
    except Exception as e:
        logger.warning(f'Congressional trades failed: {e}')
        return f'Congressional trade data unavailable: {str(e)}'


def get_stock_act_filings(ticker: str = None, lookback_days: int = 45) -> str:
    """Fetch STOCK Act filings, optionally filtered by company/ticker name."""
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        query = f'"{ticker}"' if ticker else '"purchase" OR "sale"'
        url = 'https://efts.sec.gov/LATEST/search-index'
        params = {'q': query, 'forms': '4',
                  'dateRange': 'custom', 'startdt': start_date, 'enddt': end_date}
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        hits = data.get('hits', {}).get('hits', [])
        total = data.get('hits', {}).get('total', {}).get('value', 0)
        if not hits:
            return f'No STOCK Act filings for {ticker or "general"} in last {lookback_days} days.'
        label = ticker if ticker else 'all assets'
        output = f'STOCK Act Filings for {label} ({start_date} to {end_date}):\n'
        output += f'Total: {total} filings\n\n'
        for i, hit in enumerate(hits[:10], 1):
            src = hit.get('_source', {})
            names = src.get('display_names', [])
            name_str = names[0][:60] if names else 'N/A'
            output += f'{i}. {name_str} | {src.get("file_date", "N/A")} | Form {src.get("form", "N/A")}\n'
        logger.info(f'STOCK Act filings fetched for {label}: {len(hits)} results (total: {total})')
        return output
    except Exception as e:
        logger.warning(f'STOCK Act filings failed: {e}')
        return f'STOCK Act data unavailable: {str(e)}'
