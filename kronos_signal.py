import os, sys, json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Add repo path (git clone fallback install)
_repo = os.getenv("KRONOS_REPO", "/root/kronos_repo")
if _repo and _repo not in sys.path:
    sys.path.insert(0, _repo)

# Local model cache paths (pre-downloaded to avoid HF timeout issues)
TOKENIZER_PATH = "/root/.cache/kronos_models/tokenizer"
MODEL_PATH = "/root/.cache/kronos_models/model"

def get_kronos_signal(lookback_bars: int = 168) -> dict:
    """
    Layer 10: Kronos financial time-series forecast.
    lookback_bars=168 = 28 days of 4h candles. Max context: 512.
    Uses Kronos-mini + Kronos-Tokenizer-base (pre-cached locally).
    CPU inference, ~15-60 seconds depending on context length.
    Returns compressed signal dict.
    """
    try:
        import torch
        import yfinance as yf
        from model.kronos import Kronos, KronosTokenizer, KronosPredictor

        # Fetch BTC 4h OHLCV
        df = yf.Ticker("BTC-USD").history(period="32d", interval="4h").dropna()
        if len(df) < 30:
            return {"signal": "NEUTRAL", "conf": 0.0, "err": "insufficient_data"}

        # Kronos expects lowercase column names
        df.columns = [c.lower() for c in df.columns]

        # yfinance 4h data has DatetimeIndex — preserve as x_timestamp
        timestamps = df.index.to_series().reset_index(drop=True)

        # Keep OHLCV, add 'amount' column (Kronos wants it)
        ohlcv = df[['open', 'high', 'low', 'close', 'volume']].copy()
        ohlcv['amount'] = ohlcv['volume'] * ohlcv['close']
        ohlcv = ohlcv.reset_index(drop=True)

        # Cap at max context
        max_bars = min(lookback_bars, 512)
        if len(ohlcv) > max_bars:
            ohlcv = ohlcv.iloc[-max_bars:].reset_index(drop=True)
            timestamps = timestamps.iloc[-max_bars:].reset_index(drop=True)

        current_close = float(ohlcv['close'].iloc[-1])

        # Generate future timestamp (next 4h bar)
        last_ts = timestamps.iloc[-1]
        y_timestamp = pd.Series([last_ts + timedelta(hours=4)])

        # Load model + tokenizer from local cache
        tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_PATH)
        model = Kronos.from_pretrained(MODEL_PATH)
        predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)

        # Predict next bar
        pred_df = predictor.predict(
            df=ohlcv,
            x_timestamp=timestamps,
            y_timestamp=y_timestamp,
            pred_len=1,
            T=1.0,
            top_p=0.9,
            sample_count=1,
            verbose=False
        )

        pred_close = float(pred_df['close'].iloc[0])
        pct_change = (pred_close - current_close) / current_close * 100

        # Signal logic: direction from predicted change, confidence from magnitude
        if pct_change > 0.3:
            sig = "BULLISH"
            conf = min(0.55 + abs(pct_change) * 0.08, 0.95)
        elif pct_change < -0.3:
            sig = "BEARISH"
            conf = min(0.55 + abs(pct_change) * 0.08, 0.95)
        else:
            sig = "NEUTRAL"
            conf = 0.50

        return {
            "signal": sig, "conf": round(conf, 3),
            "pred_close": round(pred_close, 2), "current": round(current_close, 2),
            "pct": round(pct_change, 4), "bars": len(ohlcv),
            "ts": datetime.utcnow().isoformat()
        }
    except ImportError as e:
        return {"signal": "NEUTRAL", "conf": 0.0, "err": f"import:{e}"}
    except Exception as e:
        return {"signal": "NEUTRAL", "conf": 0.0, "err": str(e)[:80]}


def fmt_kronos(r: dict) -> str:
    """Compact format — target ~40 tokens."""
    if r.get("err"):
        return f"[L10:Kronos] UNAVAIL | {r['err'][:50]}"
    return (
        f"[L10:Kronos] {r['signal']} {r['conf']:.0%} | "
        f"pred=${r['pred_close']:,.0f} now=${r['current']:,.0f} ({r['pct']:+.2f}%) | "
        f"{r['bars']}bars"
    )


if __name__ == "__main__":
    print("Testing Kronos Layer 10...")
    r = get_kronos_signal()
    print(json.dumps(r, indent=2))
    print(f"\nPipeline string ({len(fmt_kronos(r))} chars):")
    print(fmt_kronos(r))
