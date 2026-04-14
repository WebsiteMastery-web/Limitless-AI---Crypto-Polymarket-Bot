#!/usr/bin/env python3
"""
Risk Manager for Limitless AI - Production Grade
All 8 checks: confidence, drawdown, daily limit, cooldown,
consecutive losses, volatility, market regime, Alpaca connectivity.
"""
import os
import json
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv

load_dotenv("/root/limitless-ai/TradingAgents/.env")

LOGS_DIR = Path("/root/limitless-ai/logs")
RISK_STATE_FILE = LOGS_DIR / "risk_state.json"

DEFAULT_STATE = {
    "peak_equity": 0.0,
    "daily_trades": 0,
    "last_trade_date": None,
    "last_loss_time": None,
    "consecutive_losses": 0,
    "last_updated": None,
}


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------

def load_risk_state() -> Dict[str, Any]:
    if RISK_STATE_FILE.exists():
        try:
            with open(RISK_STATE_FILE) as f:
                data = json.load(f)
            for k, v in DEFAULT_STATE.items():
                data.setdefault(k, v)
            return data
        except Exception as e:
            logger.warning(f"Could not read risk state, using defaults: {e}")
    return DEFAULT_STATE.copy()


def save_risk_state(state: Dict[str, Any]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    fd, tmp_path = tempfile.mkstemp(dir=LOGS_DIR, prefix=".risk_state_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_path, str(RISK_STATE_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Alpaca helpers
# ---------------------------------------------------------------------------

def _get_alpaca_client():
    from alpaca.trading.client import TradingClient
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    return TradingClient(api_key, secret_key, paper=paper)


def _get_account_info() -> Optional[Dict[str, Any]]:
    try:
        client = _get_alpaca_client()
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "status": account.status.name if hasattr(account.status, "name") else str(account.status),
        }
    except Exception as e:
        logger.error(f"Alpaca account fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Position sizing (Kelly-based)
# ---------------------------------------------------------------------------

def calculate_position_size(
    confidence: float,
    current_price: float,
    balance: float,
    annualized_vol: float,
) -> float:
    """Return BTC quantity using Kelly fraction capped at 10%."""
    kelly_fraction = (confidence / 100 - 0.5) / max(annualized_vol, 0.3)
    kelly_fraction = max(0.01, min(kelly_fraction, 0.10))
    position_value = balance * kelly_fraction
    btc_quantity = position_value / current_price
    return round(btc_quantity, 6)


# ---------------------------------------------------------------------------
# Market data helpers
# ---------------------------------------------------------------------------

def _fetch_btc_vol_and_sma() -> Tuple[float, float, float]:
    """Returns (annualized_vol, sma20, current_price) using yfinance."""
    import yfinance as yf
    import numpy as np

    data = yf.download("BTC-USD", period="25d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 15:
        raise ValueError("Insufficient BTC price data from yfinance")

    closes = data["Close"].squeeze()
    returns = closes.pct_change().dropna().tail(14)
    annualized_vol = float(returns.std() * (365 ** 0.5))

    sma20 = float(closes.rolling(20).mean().iloc[-1])
    current = float(closes.iloc[-1])
    return annualized_vol, sma20, current


# ---------------------------------------------------------------------------
# Main risk gate
# ---------------------------------------------------------------------------

def risk_check(
    decision: str,
    confidence: float,
    current_price: float,
    balance: Optional[float] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Main risk gate.
    Returns (approved: bool, reasoning: str, result: dict).
    All 8 checks run; a single failure blocks execution.
    """
    checks = []
    all_passed = True
    annualized_vol = 0.0
    market_regime = "unknown"
    account_info = None

    # Input validation
    if not isinstance(decision, str) or decision.upper() not in ("BUY", "SELL", "HOLD"):
        raise ValueError(f"decision must be BUY/SELL/HOLD, got: {decision!r}")
    if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 100):
        raise ValueError(f"confidence must be 0-100, got: {confidence}")
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        raise ValueError(f"current_price must be positive, got: {current_price}")
    if balance is not None and (not isinstance(balance, (int, float)) or balance <= 0):
        raise ValueError(f"balance must be positive when provided, got: {balance}")

    decision_upper = decision.upper()

    def _add(name: str, passed: bool, message: str):
        nonlocal all_passed
        checks.append({"check": name, "passed": passed, "message": message})
        if not passed:
            all_passed = False

    # ------------------------------------------------------------------
    # CHECK 1 - Minimum confidence
    # ------------------------------------------------------------------
    if confidence < 65:
        _add("min_confidence", False,
             f"BLOCKED: Confidence {confidence}% below 65% minimum")
    else:
        _add("min_confidence", True,
             f"Confidence {confidence}% meets 65% minimum")

    # ------------------------------------------------------------------
    # Load state (needed for checks 2-5)
    # ------------------------------------------------------------------
    state = load_risk_state()

    # ------------------------------------------------------------------
    # CHECK 2 - Max drawdown
    # ------------------------------------------------------------------
    current_equity = balance if balance is not None else current_price
    peak = state.get("peak_equity", 0.0)
    if peak <= 0 or current_equity > peak:
        state["peak_equity"] = current_equity
        peak = current_equity
    drawdown = (peak - current_equity) / peak if peak > 0 else 0.0
    if drawdown > 0.10:
        _add("max_drawdown", False,
             f"BLOCKED: Drawdown {drawdown*100:.1f}% exceeds 10% limit")
    else:
        _add("max_drawdown", True,
             f"Drawdown {drawdown*100:.1f}% within 10% limit")

    # ------------------------------------------------------------------
    # CHECK 3 - Daily trade limit
    # ------------------------------------------------------------------
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("last_trade_date") != today:
        state["daily_trades"] = 0
        state["last_trade_date"] = today
    daily = state.get("daily_trades", 0)
    if daily >= 5:
        _add("daily_trade_limit", False,
             f"BLOCKED: Daily trade limit reached ({daily}/5)")
    else:
        _add("daily_trade_limit", True,
             f"Daily trades: {daily}/5")

    # ------------------------------------------------------------------
    # CHECK 4 - Post-loss cooldown (4 hours)
    # ------------------------------------------------------------------
    last_loss = state.get("last_loss_time")
    if last_loss:
        try:
            loss_time = datetime.fromisoformat(last_loss)
            if loss_time.tzinfo is None:
                loss_time = loss_time.replace(tzinfo=timezone.utc)
            cooldown_end = loss_time + timedelta(hours=4)
            now = datetime.now(timezone.utc)
            if now < cooldown_end:
                remaining_h = (cooldown_end - now).total_seconds() / 3600
                _add("post_loss_cooldown", False,
                     f"BLOCKED: Loss cooldown active, {remaining_h:.1f}h remaining")
            else:
                _add("post_loss_cooldown", True, "Post-loss cooldown cleared")
        except Exception as e:
            logger.error(f"Cooldown parse error: {e}")
            _add("post_loss_cooldown", False, f"BLOCKED: Cooldown check failed (state corrupted): {e}")
    else:
        _add("post_loss_cooldown", True, "No recent losses recorded")

    # ------------------------------------------------------------------
    # CHECK 5 - Consecutive loss circuit breaker (>= 3 losses -> 24h block)
    # ------------------------------------------------------------------
    consec = state.get("consecutive_losses", 0)
    if consec >= 3:
        if last_loss:
            try:
                loss_time = datetime.fromisoformat(last_loss)
                if loss_time.tzinfo is None:
                    loss_time = loss_time.replace(tzinfo=timezone.utc)
                block_end = loss_time + timedelta(hours=24)
                now = datetime.now(timezone.utc)
                if now < block_end:
                    remaining_h = (block_end - now).total_seconds() / 3600
                    _add("consecutive_loss_breaker", False,
                         f"BLOCKED: {consec} consecutive losses, circuit breaker active, "
                         f"{remaining_h:.1f}h remaining")
                else:
                    state["consecutive_losses"] = 0
                    _add("consecutive_loss_breaker", True,
                         "Circuit breaker 24h elapsed, counter reset")
            except Exception as e:
                logger.error(f"Circuit breaker parse error: {e}")
                _add("consecutive_loss_breaker", False,
                     f"BLOCKED: Circuit breaker check failed (state corrupted): {e}")
        else:
            _add("consecutive_loss_breaker", True,
                 "Circuit breaker: no loss timestamp, proceeding")
    else:
        _add("consecutive_loss_breaker", True,
             f"Consecutive losses: {consec}/3")

    # ------------------------------------------------------------------
    # CHECK 6 - Volatility-scaled confidence requirement
    # ------------------------------------------------------------------
    sma20 = current_price
    btc_live = current_price
    try:
        annualized_vol, sma20, btc_live = _fetch_btc_vol_and_sma()
        vol_pct = annualized_vol * 100
        if annualized_vol > 1.2:
            required = 80
        elif annualized_vol > 0.8:
            required = 72
        else:
            required = 65
        if confidence < required:
            _add("volatility_confidence", False,
                 f"BLOCKED: Volatility {vol_pct:.0f}% requires confidence >={required}%, "
                 f"got {confidence}%")
        else:
            _add("volatility_confidence", True,
                 f"Volatility {vol_pct:.0f}% OK, confidence {confidence}% meets {required}% requirement")
    except Exception as e:
        annualized_vol = 1.0
        _add("volatility_confidence", False,
             f"BLOCKED: Cannot fetch BTC volatility data: {e}")

    # ------------------------------------------------------------------
    # CHECK 7 - Market regime gate for BUY signals
    # ------------------------------------------------------------------
    if decision_upper == "BUY":
        regime_threshold = sma20 * 0.98
        if btc_live < regime_threshold:
            market_regime = "bearish"
            if confidence < 80:
                _add("market_regime", False,
                     f"BLOCKED: BTC ({btc_live:.0f}) below 20-SMA*0.98 "
                     f"({regime_threshold:.0f}), requires confidence>=80%, got {confidence}%")
            else:
                _add("market_regime", True,
                     f"Bearish regime but confidence {confidence}% >= 80% override")
        else:
            market_regime = "bullish"
            _add("market_regime", True,
                 f"Market regime OK: BTC {btc_live:.0f} above SMA threshold {regime_threshold:.0f}")
    else:
        market_regime = "bearish" if btc_live < sma20 * 0.98 else "bullish"
        _add("market_regime", True,
             f"Market regime check skipped for {decision_upper}")

    # ------------------------------------------------------------------
    # CHECK 8 - Alpaca account connectivity (BUY/SELL only)
    # ------------------------------------------------------------------
    if decision_upper in ("BUY", "SELL"):
        account_info = _get_account_info()
        if account_info is None:
            _add("alpaca_connectivity", False,
                 "BLOCKED: Cannot reach Alpaca -- trade execution unsafe")
        elif not any(s in account_info.get("status", "").upper() for s in ("ACTIVE", "APPROVED")):
            _add("alpaca_connectivity", False,
                 f"BLOCKED: Alpaca account status '{account_info.get('status')}' not active")
        else:
            if balance is None:
                balance = account_info["equity"]
            _add("alpaca_connectivity", True,
                 f"Alpaca connected, equity ${account_info['equity']:,.2f}, "
                 f"status {account_info.get('status')}")
    else:
        _add("alpaca_connectivity", True,
             "Alpaca connectivity check skipped for HOLD")

    # ------------------------------------------------------------------
    # Final balance for position sizing
    # ------------------------------------------------------------------
    effective_balance = balance if balance is not None else 100000.0

    position_size = calculate_position_size(
        confidence, current_price, effective_balance, annualized_vol
    )

    # ------------------------------------------------------------------
    # Persist state
    # ------------------------------------------------------------------
    save_risk_state(state)

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------
    failed = [c for c in checks if not c["passed"]]
    if failed:
        reasoning = "; ".join(c["message"] for c in failed)
    else:
        reasoning = (
            f"APPROVED: All {len(checks)} checks passed | "
            f"position {position_size} BTC | vol {annualized_vol*100:.0f}% | "
            f"regime {market_regime}"
        )

    # Dynamic ATR-based stop loss
    atr_stop_data = get_atr_stop()
    stop_loss_pct = atr_stop_data["stop_loss_pct"] if atr_stop_data else 3.0

    result = {
        "approved": all_passed,
        "checks": checks,
        "position_size": position_size,
        "annualized_volatility": round(annualized_vol, 4),
        "market_regime": market_regime,
        "account": account_info,
        "stop_loss_pct": stop_loss_pct,
    }

    return all_passed, reasoning, result


# ---------------------------------------------------------------------------
# Trade outcome recording
# ---------------------------------------------------------------------------

def record_trade_outcome(symbol: str, pnl: float) -> None:
    """Call after each completed trade to update state."""
    state = load_risk_state()
    state["daily_trades"] = state.get("daily_trades", 0) + 1
    if pnl < 0:
        state["last_loss_time"] = datetime.now(timezone.utc).isoformat()
        state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
    else:
        state["consecutive_losses"] = 0
    save_risk_state(state)
    logger.info(
        f"Trade recorded: {symbol} PnL={pnl:.2f}, "
        f"consecutive_losses={state['consecutive_losses']}"
    )


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

def get_atr_stop(symbol="BTC/USD", period=14, lookback_days=30):
    """Calculate dynamic ATR-based stop loss percentage."""
    try:
        import yfinance as yf
        ticker = yf.Ticker("BTC-USD")
        df = ticker.history(period=f"{lookback_days}d", interval="4h")
        if df.empty or len(df) < period + 1:
            return None
        df['high_low'] = df['High'] - df['Low']
        df['high_prev_close'] = abs(df['High'] - df['Close'].shift(1))
        df['low_prev_close'] = abs(df['Low'] - df['Close'].shift(1))
        df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
        atr = df['true_range'].rolling(period).mean().iloc[-1]
        atr_3ct = (atr / df['Close'].iloc[-1]) * 100
        atr_stop_pct = atr_3ct * 2.0
        stop_3ct = max(1.5, min(atr_stop_pct, 5.0))
        print(f"ATR stop: {stop_3ct:.2f}% (ATR={atr_3ct:.3f}%)")
        return {
            "atr_3ct": round(atr_3ct, 3),
            "stop_loss_pct": round(stop_3ct, 2),
            "current_price": round(df['Close'].iloc[-1], 2)
        }
    except Exception as e:
        print(f"ATR fetch failed: {e}, using fallback 3.0%")
        return {"stop_loss_pct": 3.0, "fallback": True}


if __name__ == "__main__":
    print("=== RISK MANAGER TEST ===")
    approved, reasoning, details = risk_check("BUY", 75, 85000.0, 100000.0)
    print(f"Approved: {approved}")
    print(f"Reasoning: {reasoning}")
    for c in details.get("checks", []):
        icon = "Y" if c["passed"] else "N"
        print(f"  [{icon}] {c['check']}: {c['message']}")
    print(f"Position size: {details.get('position_size')} BTC")
    print(f"Volatility: {details.get('annualized_volatility')}")
    print(f"Market regime: {details.get('market_regime')}")


