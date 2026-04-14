import os, pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, CryptoLatestBarRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger
load_dotenv("/root/limitless-ai/TradingAgents/.env")

def get_data_client():
    return CryptoHistoricalDataClient()

def get_ohlcv(symbol="BTC/USD", interval="1Day", lookback_days=90):
    client = get_data_client()
    tf = TimeFrame.Day if "Day" in interval else TimeFrame.Hour
    req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=tf,
                            start=datetime.now()-timedelta(days=lookback_days))
    bars = client.get_crypto_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.droplevel(0)
    logger.info(f"Fetched {len(df)} bars for {symbol}")
    return df

def get_current_price(symbol="BTC/USD"):
    client = get_data_client()
    req = CryptoLatestBarRequest(symbol_or_symbols=symbol)
    bar = client.get_crypto_latest_bar(req)
    price = float(bar[symbol].close)
    logger.info(f"Current {symbol} price: {price}")
    return price

def get_paper_balance():
    from alpaca.trading.client import TradingClient
    client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)
    account = client.get_account()
    return {"buying_power": float(account.buying_power), "equity": float(account.equity)}


def get_atr(symbol="BTC/USD", period=14, lookback_days=30):
    """Calculate Average True Range for dynamic stop loss."""
    import yfinance as yf
    import numpy as np

    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(period=f"{lookback_days}d", interval="4h")
    
    if df.empty or len(df) < period + 1:
        return None
    
    if hasattr(df.columns, 'droplevel'):
        df = df.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df
    
    df['high_low'] = df['High'] - df['Low']
    df['high_prev_close'] = abs(df['High'] - df['Close'].shift(1))
    df['low_prev_close'] = abs(df['Low'] - df['Close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    
    atr = df['true_range'].rolling(period).mean().iloc[-1]
    atr_3ct = (atr / df['Close'].iloc[-1]) * 100
    
    return {
        "atr_usd": round(atr, 2),
        "atr_pct": round(atr_3ct, 3),
        "current_price": round(df['Close'].iloc[-1], 2),
        "lookback": f"{period}-period 4h ATR"
    }
