#!/usr/bin/env python3
"""
Knowledge Base Updater for Limitless AI Trading System
Fetches real data from GDELT, EDGAR, yfinance, FRED, and Reddit
"""

import os
import sys
import json
import time
import logging
import requests
import io
import csv
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
    import yfinance as yf
except ImportError:
    print("ERROR: pandas/yfinance not available. Install in venv.")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KB_DIR = Path("/root/limitless-ai/knowledge_base")
KB_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def safe_float(val, default=0.0):
    """Safely parse a float, handling comma-separated strings (GDELT tone format)."""
    try:
        if val is None or val == "" or val == ".":
            return default
        s = str(val).split(",")[0].strip()
        return float(s)
    except (ValueError, TypeError):
        return default


def http_get(url, headers=None, timeout=30, retries=3):
    """GET with retries and backoff."""
    default_headers = {"User-Agent": "LimitlessAI-KnowledgeBase/1.0 (trading research)"}
    if headers:
        default_headers.update(headers)
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=default_headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt < retries - 1:
                wait = 2**attempt
                logger.warning(f"Request failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"All retries failed for {url}: {e}")
                return None
    return None


# ─────────────────────────────────────────────
# DATA SOURCE 1: GDELT — geopolitical_btc_history.md
# ─────────────────────────────────────────────


def fetch_gdelt_tone(keyword, days_back=90):
    """Fetch GDELT tone scores for a keyword over recent days."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)

    # GDELT GKG CSV query
    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str = end_dt.strftime("%Y%m%d%H%M%S")

    url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={requests.utils.quote(keyword)}"
        f"&mode=timelineTone&format=json"
        f"&startdatetime={start_str}&enddatetime={end_str}"
        f"&smoothing=5"
    )

    resp = http_get(url, timeout=45)
    if not resp:
        return []

    try:
        data = resp.json()
        results = []
        timeline = data.get("timeline", [])
        if timeline and isinstance(timeline, list):
            for item in timeline:
                series = item.get("data", [])
                for point in series:
                    date = point.get("date", "")
                    tone_raw = point.get("value", 0)
                    tone = safe_float(tone_raw)
                    results.append({"date": date, "tone": tone})
        return results
    except Exception as e:
        logger.error(f"GDELT parse error: {e}")
        return []


def update_geopolitical_btc_history():
    """Generate geopolitical_btc_history.md using GDELT tone data."""
    logger.info("Updating geopolitical_btc_history.md...")

    keywords = ["bitcoin", "cryptocurrency", "BTC price", "crypto market"]
    all_data = {}

    for kw in keywords:
        logger.info(f"  Fetching GDELT tone for: {kw}")
        results = fetch_gdelt_tone(kw, days_back=60)
        if results:
            all_data[kw] = results
        time.sleep(2)  # Rate limiting

    # Also try GDELT summary query for recent events
    geo_events = []
    try:
        now = datetime.utcnow()
        start = (now - timedelta(days=30)).strftime("%Y%m%d%H%M%S")
        end = now.strftime("%Y%m%d%H%M%S")
        url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc?"
            f"query=bitcoin%20cryptocurrency"
            f"&mode=artlist&format=json&maxrecords=20"
            f"&startdatetime={start}&enddatetime={end}"
        )
        resp = http_get(url, timeout=45)
        if resp:
            data = resp.json()
            articles = data.get("articles", [])
            for art in articles[:15]:
                title = art.get("title", "")
                tone_raw = art.get("tone", 0)
                tone = safe_float(tone_raw)
                date = art.get("seendate", "")[:8]
                url_art = art.get("url", "")
                if title:
                    geo_events.append(
                        {"date": date, "title": title, "tone": tone, "url": url_art}
                    )
    except Exception as e:
        logger.error(f"GDELT article fetch error: {e}")

    # Calculate average tones
    tone_summary = {}
    for kw, results in all_data.items():
        if results:
            tones = [r["tone"] for r in results if r["tone"] != 0.0]
            if tones:
                tone_summary[kw] = {
                    "avg": sum(tones) / len(tones),
                    "latest": tones[-1] if tones else 0.0,
                    "count": len(tones),
                }

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Geopolitical & Media Sentiment — BTC History",
        f"\n_Last updated: {now_str}_\n",
        "## Overview",
        "Tone scores from GDELT global media analysis. Scale: negative = bearish coverage, positive = bullish.",
        "Score range typically -10 to +10. Data sourced from millions of news articles worldwide.\n",
        "## Current Media Tone by Topic",
    ]

    if tone_summary:
        for kw, stats in tone_summary.items():
            sentiment = (
                "BULLISH"
                if stats["avg"] > 0.5
                else ("BEARISH" if stats["avg"] < -0.5 else "NEUTRAL")
            )
            lines.append(f"\n### {kw.title()}")
            lines.append(f"- Average Tone (60d): {stats['avg']:.2f} → **{sentiment}**")
            lines.append(f"- Latest Tone: {stats['latest']:.2f}")
            lines.append(f"- Data Points: {stats['count']}")
    else:
        lines.append(
            "\n_GDELT timeline data currently unavailable — using article-level data below._"
        )

    if geo_events:
        lines.append("\n## Recent Geopolitical Events (Last 30 Days)")
        lines.append("| Date | Tone | Headline |")
        lines.append("|------|------|----------|")
        for ev in sorted(geo_events, key=lambda x: x["date"], reverse=True)[:15]:
            date_fmt = (
                ev["date"][:4] + "-" + ev["date"][4:6] + "-" + ev["date"][6:8]
                if len(ev["date"]) >= 8
                else ev["date"]
            )
            tone_val = ev["tone"]
            lines.append(f"| {date_fmt} | {tone_val:.2f} | {ev['title'][:80]} |")

    lines.append("\n## Trading Implications")
    if tone_summary:
        overall_tones = [s["avg"] for s in tone_summary.values()]
        overall_avg = sum(overall_tones) / len(overall_tones)
        if overall_avg > 1.0:
            implication = "Media sentiment strongly bullish — favorable macro narrative for BTC accumulation."
        elif overall_avg > 0:
            implication = "Media sentiment mildly positive — monitor for confirmation."
        elif overall_avg > -1.0:
            implication = "Media sentiment mildly negative — caution advised, watch for reversal signals."
        else:
            implication = "Media sentiment strongly negative — risk-off environment, defensive positioning preferred."
        lines.append(f"\n{implication}")
    else:
        lines.append(
            "\nInsufficient data for implication — check GDELT API availability."
        )

    content = "\n".join(lines) + "\n"
    (KB_DIR / "geopolitical_btc_history.md").write_text(content, encoding="utf-8")
    logger.info("  geopolitical_btc_history.md written.")


# ─────────────────────────────────────────────
# DATA SOURCE 2: SEC EDGAR — congressional_patterns.md
# ─────────────────────────────────────────────


def fetch_edgar_form4(ticker="MSTR", count=10):
    """Fetch recent Form 4 (insider trading) filings from SEC EDGAR."""
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={(datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')}&enddt={datetime.utcnow().strftime('%Y-%m-%d')}&forms=4"

    headers = {
        "User-Agent": "LimitlessAI Research contact@limitless-ai.com",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=4&dateRange=custom"
            f"&startdt={(datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')}"
            f"&enddt={datetime.utcnow().strftime('%Y-%m-%d')}",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("hits", {}).get("hits", [])
    except Exception as e:
        logger.error(f"EDGAR form4 error for {ticker}: {e}")
    return []


def fetch_edgar_full_text_search(query, form_type="4"):
    """Use EDGAR full-text search for crypto-related filings."""
    url = (
        f"https://efts.sec.gov/LATEST/search-index?"
        f"q=%22{requests.utils.quote(query)}%22"
        f"&forms={form_type}"
        f"&dateRange=custom"
        f"&startdt={(datetime.utcnow() - timedelta(days=60)).strftime('%Y-%m-%d')}"
        f"&enddt={datetime.utcnow().strftime('%Y-%m-%d')}"
    )
    headers = {"User-Agent": "LimitlessAI Research contact@limitless-ai.com"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"EDGAR search error: {e}")
    return {}


def update_congressional_patterns():
    """Generate congressional_patterns.md using SEC EDGAR data."""
    logger.info("Updating congressional_patterns.md...")

    # Target crypto-related companies for Form 4 filings
    tickers = ["MSTR", "COIN", "RIOT", "MARA", "CLSK"]
    all_filings = []

    for ticker in tickers:
        logger.info(f"  Fetching EDGAR Form 4 for {ticker}...")
        try:
            url = f"https://data.sec.gov/submissions/CIK"
            # Use EDGAR company search
            search_url = (
                f"https://efts.sec.gov/LATEST/search-index?"
                f"q=%22{ticker}%22&forms=4"
                f"&dateRange=custom"
                f"&startdt={(datetime.utcnow() - timedelta(days=60)).strftime('%Y-%m-%d')}"
                f"&enddt={datetime.utcnow().strftime('%Y-%m-%d')}"
            )
            headers = {"User-Agent": "LimitlessAI Research contact@limitless-ai.com"}
            resp = requests.get(search_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])
                for hit in hits[:5]:
                    src = hit.get("_source", {})
                    all_filings.append(
                        {
                            "ticker": ticker,
                            "date": src.get(
                                "period_of_report", src.get("file_date", "N/A")
                            ),
                            "filer": src.get("display_names", ["Unknown"])[0]
                            if src.get("display_names")
                            else "Unknown",
                            "form": src.get("form_type", "4"),
                            "description": src.get("entity_name", ticker),
                        }
                    )
        except Exception as e:
            logger.error(f"EDGAR error for {ticker}: {e}")
        time.sleep(1)

    # Also fetch crypto ETF related 13F filings
    etf_data = []
    try:
        url = (
            f"https://efts.sec.gov/LATEST/search-index?"
            f"q=%22bitcoin%22+%22ETF%22&forms=13F-HR"
            f"&dateRange=custom"
            f"&startdt={(datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')}"
            f"&enddt={datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        headers = {"User-Agent": "LimitlessAI Research contact@limitless-ai.com"}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:10]:
                src = hit.get("_source", {})
                etf_data.append(
                    {
                        "date": src.get(
                            "period_of_report", src.get("file_date", "N/A")
                        ),
                        "filer": src.get("display_names", ["Unknown"])[0]
                        if src.get("display_names")
                        else "Unknown",
                        "form": "13F-HR",
                    }
                )
    except Exception as e:
        logger.error(f"EDGAR 13F error: {e}")

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Congressional & Institutional Trading Patterns",
        f"\n_Last updated: {now_str}_\n",
        "## Overview",
        "Insider and institutional filing data from SEC EDGAR. Form 4 = insider transactions.",
        "13F-HR = institutional holdings (>$100M AUM). Focus on crypto-adjacent companies.\n",
        "## Recent Form 4 Insider Transactions (Crypto Companies)",
    ]

    if all_filings:
        lines.append("\n| Date | Ticker | Filer | Form |")
        lines.append("|------|--------|-------|------|")
        for f in sorted(all_filings, key=lambda x: x["date"], reverse=True)[:20]:
            lines.append(
                f"| {f['date']} | {f['ticker']} | {f['filer'][:40]} | {f['form']} |"
            )
    else:
        lines.append(
            "\n_No Form 4 filings found in the past 60 days for monitored tickers._"
        )

    if etf_data:
        lines.append("\n## Bitcoin ETF Institutional Holdings (13F Filings)")
        lines.append("\n| Date | Institution |")
        lines.append("|------|-------------|")
        for f in sorted(etf_data, key=lambda x: x["date"], reverse=True)[:10]:
            lines.append(f"| {f['date']} | {f['filer'][:60]} |")

    lines.append("\n## Trading Implications")
    total = len(all_filings)
    if total > 10:
        lines.append(
            f"\nHigh insider activity ({total} filings in 60 days) — monitor direction of transactions."
        )
    elif total > 0:
        lines.append(
            f"\nModerate insider activity ({total} filings) — normal institutional behavior."
        )
    else:
        lines.append(
            "\nLow insider filing activity — no unusual institutional signals detected."
        )

    content = "\n".join(lines) + "\n"
    (KB_DIR / "congressional_patterns.md").write_text(content, encoding="utf-8")
    logger.info("  congressional_patterns.md written.")


# ─────────────────────────────────────────────
# DATA SOURCE 3: yfinance — trading_strategies.md
# ─────────────────────────────────────────────


def get_btc_price_yfinance(date_str):
    """Get BTC-USD close price for a specific date using yfinance."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        next_day = dt + timedelta(days=1)
        next_day_str = next_day.strftime("%Y-%m-%d")

        data = yf.download(
            "BTC-USD",
            start=date_str,
            end=next_day_str,
            progress=False,
            auto_adjust=True,
        )
        if not data.empty:
            close = data["Close"].iloc[0]
            # Handle both scalar and Series
            if hasattr(close, "iloc"):
                close = close.iloc[0]
            return float(close)
    except Exception as e:
        logger.error(f"yfinance error for {date_str}: {e}")
    return None


def flatten_yf_columns(df):
    """Flatten MultiIndex columns from yfinance to simple column names."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df


def update_trading_strategies():
    """Generate trading_strategies.md with real BTC price data from yfinance."""
    logger.info("Updating trading_strategies.md...")

    # Get BTC data for past year
    try:
        btc_1y = flatten_yf_columns(
            yf.download("BTC-USD", period="1y", progress=False, auto_adjust=True)
        )
        btc_3m = flatten_yf_columns(
            yf.download("BTC-USD", period="3mo", progress=False, auto_adjust=True)
        )
        btc_1m = flatten_yf_columns(
            yf.download("BTC-USD", period="1mo", progress=False, auto_adjust=True)
        )
    except Exception as e:
        logger.error(f"yfinance download error: {e}")
        btc_1y = pd.DataFrame()
        btc_3m = pd.DataFrame()
        btc_1m = pd.DataFrame()

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    lines = [
        "# BTC Trading Strategies & Historical Price Analysis",
        f"\n_Last updated: {now_str}_\n",
    ]

    # Current price stats
    if not btc_1m.empty:
        current_close = btc_1m["Close"]
        if hasattr(current_close, "squeeze"):
            current_close = current_close.squeeze()

        latest_price = float(current_close.iloc[-1])
        month_high = float(current_close.max())
        month_low = float(current_close.min())
        month_open = float(current_close.iloc[0])
        month_return = ((latest_price - month_open) / month_open) * 100

        lines.append("## Current BTC Price Statistics")
        lines.append(f"\n- **Current Price**: ${latest_price:,.2f}")
        lines.append(f"- **30-Day High**: ${month_high:,.2f}")
        lines.append(f"- **30-Day Low**: ${month_low:,.2f}")
        lines.append(f"- **30-Day Return**: {month_return:+.2f}%")

    if not btc_3m.empty:
        close_3m = btc_3m["Close"]
        if hasattr(close_3m, "squeeze"):
            close_3m = close_3m.squeeze()

        q_high = float(close_3m.max())
        q_low = float(close_3m.min())
        q_open = float(close_3m.iloc[0])
        q_latest = float(close_3m.iloc[-1])
        q_return = ((q_latest - q_open) / q_open) * 100
        q_vol = float(close_3m.pct_change().std() * (252**0.5) * 100)

        lines.append(f"\n## 3-Month Performance")
        lines.append(f"\n- **3M High**: ${q_high:,.2f}")
        lines.append(f"- **3M Low**: ${q_low:,.2f}")
        lines.append(f"- **3M Return**: {q_return:+.2f}%")
        lines.append(f"- **Annualized Volatility**: {q_vol:.1f}%")

    if not btc_1y.empty:
        close_1y = btc_1y["Close"]
        if hasattr(close_1y, "squeeze"):
            close_1y = close_1y.squeeze()

        y_high = float(close_1y.max())
        y_low = float(close_1y.min())
        y_open = float(close_1y.iloc[0])
        y_latest = float(close_1y.iloc[-1])
        y_return = ((y_latest - y_open) / y_open) * 100
        y_vol = float(close_1y.pct_change().std() * (252**0.5) * 100)

        # Calculate drawdown
        rolling_max = close_1y.cummax()
        drawdown = (close_1y - rolling_max) / rolling_max * 100
        max_drawdown = float(drawdown.min())

        # Simple moving averages
        sma50 = (
            float(close_1y.rolling(50).mean().iloc[-1]) if len(close_1y) >= 50 else None
        )
        sma200 = (
            float(close_1y.rolling(200).mean().iloc[-1])
            if len(close_1y) >= 200
            else None
        )

        lines.append(f"\n## 1-Year Performance")
        lines.append(f"\n- **52-Week High**: ${y_high:,.2f}")
        lines.append(f"- **52-Week Low**: ${y_low:,.2f}")
        lines.append(f"- **1Y Return**: {y_return:+.2f}%")
        lines.append(f"- **Annualized Volatility**: {y_vol:.1f}%")
        lines.append(f"- **Max Drawdown (1Y)**: {max_drawdown:.1f}%")
        if sma50:
            lines.append(f"- **50-Day SMA**: ${sma50:,.2f}")
        if sma200:
            lines.append(f"- **200-Day SMA**: ${sma200:,.2f}")

        # Trend signal
        if sma50 and sma200:
            if sma50 > sma200:
                signal = "BULLISH (Golden Cross: 50 SMA > 200 SMA)"
            else:
                signal = "BEARISH (Death Cross: 50 SMA < 200 SMA)"
            lines.append(f"- **MA Signal**: {signal}")

        # Monthly breakdown (last 6 months)
        lines.append("\n## Monthly Price History (Last 6 Months)")
        lines.append("\n| Month | Open | High | Low | Close | Return |")
        lines.append("|-------|------|------|-----|-------|--------|")

        btc_monthly = btc_1y.resample("ME").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        )
        btc_monthly = btc_monthly.tail(6)

        for idx, row in btc_monthly.iterrows():
            month_str = idx.strftime("%Y-%m")
            try:
                o = (
                    float(row["Open"].iloc[0])
                    if hasattr(row["Open"], "iloc")
                    else float(row["Open"])
                )
                h = (
                    float(row["High"].iloc[0])
                    if hasattr(row["High"], "iloc")
                    else float(row["High"])
                )
                l = (
                    float(row["Low"].iloc[0])
                    if hasattr(row["Low"], "iloc")
                    else float(row["Low"])
                )
                c = (
                    float(row["Close"].iloc[0])
                    if hasattr(row["Close"], "iloc")
                    else float(row["Close"])
                )
                ret = ((c - o) / o) * 100
                lines.append(
                    f"| {month_str} | ${o:,.0f} | ${h:,.0f} | ${l:,.0f} | ${c:,.0f} | {ret:+.1f}% |"
                )
            except Exception as e:
                logger.warning(f"Row parse error for {month_str}: {e}")

    lines.append("\n## Trading Strategy Signals")
    if not btc_1m.empty:
        current_close = btc_1m["Close"]
        if hasattr(current_close, "squeeze"):
            current_close = current_close.squeeze()
        latest = float(current_close.iloc[-1])
        rsi_period = 14
        if len(current_close) > rsi_period:
            delta = current_close.diff()
            gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            if rsi > 70:
                rsi_signal = f"OVERBOUGHT ({rsi:.1f}) — consider reducing exposure"
            elif rsi < 30:
                rsi_signal = f"OVERSOLD ({rsi:.1f}) — potential buying opportunity"
            else:
                rsi_signal = f"NEUTRAL ({rsi:.1f}) — no strong RSI signal"

            lines.append(f"\n- **RSI (14)**: {rsi_signal}")

        lines.append(
            f"- **Current Price vs 30d avg**: ${latest:,.2f} vs ${float(current_close.mean()):,.2f}"
        )

    content = "\n".join(lines) + "\n"
    (KB_DIR / "trading_strategies.md").write_text(content, encoding="utf-8")
    logger.info("  trading_strategies.md written.")


# ─────────────────────────────────────────────
# DATA SOURCE 4: FRED — macro_context.md
# ─────────────────────────────────────────────


def fetch_fred_series(series_id):
    """Fetch a FRED data series as a DataFrame."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    headers = {"User-Agent": "LimitlessAI-MacroResearch/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        # Parse CSV, skipping comment lines
        lines = [l for l in resp.text.splitlines() if not l.startswith("#")]
        df = pd.read_csv(io.StringIO("\n".join(lines)))
        df.columns = ["date", "value"]
        df = df[df["value"] != "."].copy()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return df
    except Exception as e:
        logger.error(f"FRED fetch error for {series_id}: {e}")
        return pd.DataFrame()


def compute_trend(series, months=3):
    """Compute trend direction over last N months."""
    if series.empty or len(series) < 2:
        return "unknown"
    try:
        cutoff = series["date"].max() - pd.DateOffset(months=months)
        recent = series[series["date"] >= cutoff]
        if len(recent) < 2:
            return "unknown"
        first_val = float(recent["value"].iloc[0])
        last_val = float(recent["value"].iloc[-1])
        diff = last_val - first_val
        pct = abs(diff / first_val * 100) if first_val != 0 else 0
        if pct < 0.5:
            return "flat"
        return "rising" if diff > 0 else "falling"
    except Exception:
        return "unknown"


def update_macro_context():
    """Generate macro_context.md using FRED economic data."""
    logger.info("Updating macro_context.md...")

    series_config = {
        "FEDFUNDS": ("Federal Funds Rate", "%"),
        "DFF": ("Daily Fed Funds Rate", "%"),
        "CPIAUCSL": ("CPI (Inflation)", "index"),
        "UNRATE": ("Unemployment Rate", "%"),
        "T10Y2Y": ("10Y-2Y Yield Spread (Yield Curve)", "%"),
    }

    fetched = {}
    for sid, (name, unit) in series_config.items():
        logger.info(f"  Fetching FRED {sid}...")
        df = fetch_fred_series(sid)
        if not df.empty:
            fetched[sid] = {"name": name, "unit": unit, "data": df}
        time.sleep(1)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Macro Economic Context",
        f"\n_Last updated: {now_str}_\n",
        "## Overview",
        "Federal Reserve economic indicators relevant to BTC/crypto market conditions.",
        "Data sourced from FRED (Federal Reserve Bank of St. Louis).\n",
        "## Key Indicators",
    ]

    for sid, (name, unit) in series_config.items():
        if sid in fetched:
            d = fetched[sid]
            df = d["data"]
            latest_val = float(df["value"].iloc[-1])
            latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")
            trend = compute_trend(df, months=3)

            # Trend arrow
            arrow = "↑" if trend == "rising" else ("↓" if trend == "falling" else "→")

            lines.append(f"\n### {name} ({sid})")
            lines.append(f"- **Current Value**: {latest_val:.3f} {unit}")
            lines.append(f"- **As of**: {latest_date}")
            lines.append(f"- **3-Month Trend**: {trend.upper()} {arrow}")

            # Add context
            if sid == "FEDFUNDS" or sid == "DFF":
                if latest_val > 5.0:
                    ctx = "High rates — risk-off environment, headwind for BTC"
                elif latest_val > 3.0:
                    ctx = "Elevated rates — moderate headwind for risk assets"
                elif latest_val < 1.0:
                    ctx = "Near-zero rates — historically bullish for BTC/crypto"
                else:
                    ctx = "Moderate rates — neutral macro environment"
                lines.append(f"- **Context**: {ctx}")

            elif sid == "T10Y2Y":
                if latest_val < 0:
                    ctx = "INVERTED yield curve — recession signal, risk-off"
                elif latest_val < 0.5:
                    ctx = "Flat/near-inverted — caution warranted"
                else:
                    ctx = "Normal yield curve — growth expectations intact"
                lines.append(f"- **Context**: {ctx}")

            elif sid == "CPIAUCSL":
                # Calculate YoY inflation
                try:
                    yr_ago = df[
                        df["date"] <= df["date"].max() - pd.DateOffset(years=1)
                    ].iloc[-1]
                    yoy_cpi = (
                        (latest_val - float(yr_ago["value"]))
                        / float(yr_ago["value"])
                        * 100
                    )
                    lines.append(f"- **YoY Inflation**: {yoy_cpi:.2f}%")
                    if yoy_cpi > 5:
                        ctx = "High inflation — BTC as inflation hedge narrative strengthens"
                    elif yoy_cpi > 2:
                        ctx = "Above-target inflation — mild tailwind for hard assets"
                    else:
                        ctx = "Near-target inflation — inflation not a primary driver"
                    lines.append(f"- **Context**: {ctx}")
                except Exception:
                    pass
        else:
            lines.append(f"\n### {name} ({sid})")
            lines.append(f"- **Status**: Data unavailable from FRED")

    # Overall macro stance
    lines.append("\n## Overall Macro Stance for BTC")
    stances = []
    if "FEDFUNDS" in fetched:
        rate = float(fetched["FEDFUNDS"]["data"]["value"].iloc[-1])
        rate_trend = compute_trend(fetched["FEDFUNDS"]["data"])
        if rate > 4.5 and rate_trend == "flat":
            stances.append(
                "Rates near peak — potential for future cuts (bullish catalyst)"
            )
        elif rate > 4.5 and rate_trend == "rising":
            stances.append("Rates still rising — continued headwind for risk assets")
        elif rate_trend == "falling":
            stances.append("Rate cutting cycle — historically bullish for BTC")

    if "T10Y2Y" in fetched:
        spread = float(fetched["T10Y2Y"]["data"]["value"].iloc[-1])
        if spread < 0:
            stances.append("Inverted yield curve — recession risk elevated")
        elif spread > 0.5:
            stances.append(
                "Healthy yield curve — growth expectations support risk assets"
            )

    if stances:
        for s in stances:
            lines.append(f"\n- {s}")
    else:
        lines.append("\n_Insufficient macro data for stance assessment._")

    content = "\n".join(lines) + "\n"
    (KB_DIR / "macro_context.md").write_text(content, encoding="utf-8")
    logger.info("  macro_context.md written.")


# ─────────────────────────────────────────────
# DATA SOURCE 5: Reddit — reddit_sentiment.md
# ─────────────────────────────────────────────

BULLISH_KW = {
    "moon",
    "pump",
    "buy",
    "bull",
    "breakout",
    "all-time-high",
    "ath",
    "hodl",
    "accumulate",
    "rally",
    "surge",
    "rise",
    "gain",
    "bullish",
    "long",
    "upside",
}
BEARISH_KW = {
    "crash",
    "dump",
    "sell",
    "bear",
    "dead",
    "rekt",
    "capitulate",
    "short",
    "drop",
    "fall",
    "plunge",
    "collapse",
    "loss",
    "bearish",
    "down",
    "correction",
}


def classify_post(title):
    """Classify a post title as bullish, bearish, or neutral using keyword matching."""
    title_lower = title.lower()
    bullish_kw = ["moon","pump","buy","bull","breakout","ath","hodl","accumulate","rally","green"]
    bearish_kw = ["crash","dump","sell","bear","dead","rekt","capitulate","short","fear","drop"]
    
    b = sum(1 for k in bullish_kw if k in title_lower)
    s = sum(1 for k in bearish_kw if k in title_lower)
    
    if b > s:
        return "bullish", [k for k in bullish_kw if k in title_lower]
    elif s > b:
        return "bearish", [k for k in bearish_kw if k in title_lower]
    return "neutral", []


def fetch_reddit_posts(subreddit, limit=25):
    """Fetch hot posts from a subreddit using Reddit's JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    headers = {
        "User-Agent": "LimitlessAI-SentimentBot/1.0 (trading research; contact: admin@limitless-ai.com)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            posts = []
            for child in data.get("data", {}).get("children", []):
                p = child.get("data", {})
                posts.append(
                    {
                        "title": p.get("title", ""),
                        "score": p.get("score", 0),
                        "upvote_ratio": p.get("upvote_ratio", 0.5),
                        "num_comments": p.get("num_comments", 0),
                        "url": p.get("url", ""),
                        "created": datetime.fromtimestamp(
                            p.get("created_utc", 0)
                        ).strftime("%Y-%m-%d"),
                    }
                )
            return posts
        elif resp.status_code == 429:
            logger.warning(f"Reddit rate limited for r/{subreddit}")
        else:
            logger.warning(f"Reddit API returned {resp.status_code} for r/{subreddit}")
    except Exception as e:
        logger.error(f"Reddit fetch error for r/{subreddit}: {e}")
    return []


def update_reddit_sentiment():
    """Generate reddit_sentiment.md with crypto community sentiment."""
    logger.info("Updating reddit_sentiment.md...")

    subreddits = ["Bitcoin", "CryptoCurrency", "CryptoMarkets"]
    all_posts = []

    for sub in subreddits:
        logger.info(f"  Fetching r/{sub}...")
        posts = fetch_reddit_posts(sub, limit=25)
        for p in posts:
            p["subreddit"] = sub
        all_posts.extend(posts)
        time.sleep(2)  # Be respectful of Reddit rate limits

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    lines = [
        "# Reddit Crypto Sentiment Analysis",
        f"\n_Last updated: {now_str}_\n",
    ]

    if not all_posts:
        lines.append("## Status")
        lines.append(
            "\n_Reddit API unavailable at time of update. No sentiment data collected._"
        )
    else:
        # Classify posts
        bullish_posts = []
        bearish_posts = []
        neutral_posts = []

        for p in all_posts:
            sentiment, kws = classify_post(p["title"])
            p["sentiment"] = sentiment
            p["matched_keywords"] = kws
            if sentiment == "bullish":
                bullish_posts.append(p)
            elif sentiment == "bearish":
                bearish_posts.append(p)
            else:
                neutral_posts.append(p)

        total = len(all_posts)
        bull_pct = (len(bullish_posts) / total * 100) if total > 0 else 0
        bear_pct = (len(bearish_posts) / total * 100) if total > 0 else 0
        neutral_pct = (len(neutral_posts) / total * 100) if total > 0 else 0

        # Weighted by score
        bull_score = sum(p["score"] for p in bullish_posts)
        bear_score = sum(p["score"] for p in bearish_posts)
        total_scored = bull_score + bear_score
        bull_score_pct = (bull_score / total_scored * 100) if total_scored > 0 else 0
        bear_score_pct = (bear_score / total_scored * 100) if total_scored > 0 else 0

        # Overall signal
        if bull_pct > bear_pct * 1.5:
            overall = "BULLISH"
        elif bear_pct > bull_pct * 1.5:
            overall = "BEARISH"
        else:
            overall = "MIXED/NEUTRAL"

        lines.append(f"## Reddit Crypto Sentiment — {today}")
        lines.append(f"\n**Overall Signal: {overall}**\n")
        lines.append(
            f"- Total posts analyzed: {total} (across {len(subreddits)} subreddits)"
        )
        lines.append(f"- Bullish posts: {len(bullish_posts)} ({bull_pct:.1f}%)")
        lines.append(f"- Bearish posts: {len(bearish_posts)} ({bear_pct:.1f}%)")
        lines.append(f"- Neutral/Mixed: {len(neutral_posts)} ({neutral_pct:.1f}%)")
        lines.append(f"- Score-weighted bullish: {bull_score_pct:.1f}%")
        lines.append(f"- Score-weighted bearish: {bear_score_pct:.1f}%")

        # Top posts by score
        top_posts = sorted(all_posts, key=lambda x: x["score"], reverse=True)[:10]
        lines.append("\n## Top Posts by Score")
        lines.append("\n| Score | Sentiment | Subreddit | Title |")
        lines.append("|-------|-----------|-----------|-------|")
        for p in top_posts:
            sentiment_icon = (
                "🐂"
                if p["sentiment"] == "bullish"
                else ("🐻" if p["sentiment"] == "bearish" else "➖")
            )
            title_short = (
                p["title"][:60] + "..." if len(p["title"]) > 60 else p["title"]
            )
            lines.append(
                f"| {p['score']:,} | {sentiment_icon} {p['sentiment']} | r/{p['subreddit']} | {title_short} |"
            )

        # Bullish highlights
        if bullish_posts:
            lines.append("\n## Most Upvoted Bullish Posts")
            for p in sorted(bullish_posts, key=lambda x: x["score"], reverse=True)[:5]:
                lines.append(
                    f"\n- **{p['title'][:80]}** (score: {p['score']:,}, r/{p['subreddit']})"
                )
                if p["matched_keywords"]:
                    lines.append(f"  _Keywords: {', '.join(p['matched_keywords'])}_")

        # Bearish highlights
        if bearish_posts:
            lines.append("\n## Most Upvoted Bearish Posts")
            for p in sorted(bearish_posts, key=lambda x: x["score"], reverse=True)[:5]:
                lines.append(
                    f"\n- **{p['title'][:80]}** (score: {p['score']:,}, r/{p['subreddit']})"
                )
                if p["matched_keywords"]:
                    lines.append(f"  _Keywords: {', '.join(p['matched_keywords'])}_")

        # Subreddit breakdown
        lines.append("\n## Sentiment by Subreddit")
        lines.append("\n| Subreddit | Posts | Bullish% | Bearish% |")
        lines.append("|-----------|-------|----------|----------|")
        for sub in subreddits:
            sub_posts = [p for p in all_posts if p["subreddit"] == sub]
            if sub_posts:
                sub_bull = sum(1 for p in sub_posts if p["sentiment"] == "bullish")
                sub_bear = sum(1 for p in sub_posts if p["sentiment"] == "bearish")
                sub_total = len(sub_posts)
                lines.append(
                    f"| r/{sub} | {sub_total} | {sub_bull / sub_total * 100:.0f}% | {sub_bear / sub_total * 100:.0f}% |"
                )

        lines.append("\n## Trading Implications")
        if overall == "BULLISH":
            lines.append(
                "\nRetail sentiment bullish — FOMO dynamics may push price higher short-term. Watch for contrarian signals at extremes."
            )
        elif overall == "BEARISH":
            lines.append(
                "\nRetail sentiment bearish — potential capitulation or continued selling. Watch for reversal signals."
            )
        else:
            lines.append(
                "\nMixed retail sentiment — no strong directional bias from community. Follow technical signals."
            )

    content = "\n".join(lines) + "\n"
    (KB_DIR / "reddit_sentiment.md").write_text(content, encoding="utf-8")
    logger.info("  reddit_sentiment.md written.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update Limitless AI Knowledge Base")
    parser.add_argument(
        "--full", action="store_true", help="Run full update of all sources"
    )
    parser.add_argument("--source", type=str, help="Update specific source only")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Knowledge Base Update")
    logger.info(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info("=" * 60)

    sources = {
        "geopolitical": update_geopolitical_btc_history,
        "congressional": update_congressional_patterns,
        "trading": update_trading_strategies,
        "macro": update_macro_context,
        "reddit": update_reddit_sentiment,
    }

    if args.source and args.source in sources:
        sources[args.source]()
    else:
        # Run all sources
        for name, func in sources.items():
            try:
                logger.info(f"\n{'=' * 40}")
                logger.info(f"Running: {name}")
                func()
                logger.info(f"Completed: {name}")
            except Exception as e:
                logger.error(f"FAILED: {name} — {e}", exc_info=True)

    logger.info("\n" + "=" * 60)
    logger.info("Knowledge Base Update Complete")

    # Summary
    kb_files = list(KB_DIR.glob("*.md"))
    logger.info(f"Files in knowledge_base/:")
    for f in sorted(kb_files):
        size = f.stat().st_size
        logger.info(f"  {f.name}: {size:,} bytes")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
