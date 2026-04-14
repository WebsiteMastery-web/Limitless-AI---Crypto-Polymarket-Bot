#!/usr/bin/env python3
"""
Limitless AI — KMeans Regime Detector
Detects market regime (BULL/BEAR/SIDEWAYS) from 4h BTC features.
Uses KMeans clustering on: trend, atr_normalized, rsi_14, volume_ratio.
"""

import json
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

LOGS_DIR = Path("/root/limitless-ai/logs")
REGIME_FILE = LOGS_DIR / "current_regime.json"

REGIME_PARAMS = {
    "BULL":     {"confidence_threshold": 62, "position_size_multiplier": 1.2, "bias": "BUY"},
    "BEAR":     {"confidence_threshold": 70, "position_size_multiplier": 0.8, "bias": "SELL"},
    "SIDEWAYS": {"confidence_threshold": 75, "position_size_multiplier": 0.6, "bias": "HOLD"},
}


def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _fetch_features():
    import yfinance as yf
    import pandas as pd

    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(period="90d", interval="1h")  # yfinance caps 4h at 60d; use 1h & resample
    if df.empty or len(df) < 40:
        raise ValueError("Insufficient BTC data from yfinance")

    # Resample to 4h
    df = df.resample("4h").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum"
    }).dropna()

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]

    # trend: (close - close_20_bars_ago) / close_20_bars_ago
    trend = (close - close.shift(20)) / close.shift(20)

    # ATR 14
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atr_normalized = atr14 / close

    # RSI 14
    rsi = _compute_rsi(close, 14)

    # volume ratio: volume / 20-bar avg volume
    vol_avg = vol.rolling(20).mean()
    volume_ratio = vol / vol_avg.replace(0, np.nan)

    features = {
        "trend":         trend,
        "atr_normalized": atr_normalized,
        "rsi_14":        rsi,
        "volume_ratio":  volume_ratio,
    }

    import pandas as pd
    feat_df = pd.DataFrame(features).dropna()
    if len(feat_df) < 20:
        raise ValueError(f"Too few complete feature rows: {len(feat_df)}")

    # Forward-fill one-period returns for cluster labelling
    feat_df["_return"] = close.reindex(feat_df.index).pct_change().shift(-1)
    return feat_df, close


def detect_regime():
    """
    Detect current BTC market regime using KMeans on 4h features.
    Returns dict with: regime, confidence, params, detected_at.
    Also writes /root/limitless-ai/logs/current_regime.json.
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    LOGS_DIR.mkdir(exist_ok=True)

    try:
        feat_df, close = _fetch_features()
    except Exception as e:
        logger.error(f"[REGIME] Feature fetch failed: {e}")
        return _fallback_regime(str(e))

    feature_cols = ["trend", "atr_normalized", "rsi_14", "volume_ratio"]
    X = feat_df[feature_cols].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    feat_df["_label"] = labels

    # Map clusters to regimes by mean forward return
    cluster_returns = (
        feat_df.groupby("_label")["_return"]
        .mean()
        .dropna()
        .to_dict()
    )
    # Fallback if NaN for some cluster
    for lbl in [0, 1, 2]:
        cluster_returns.setdefault(lbl, 0.0)

    sorted_clusters = sorted(cluster_returns.items(), key=lambda x: x[1])
    regime_map = {
        sorted_clusters[0][0]: "BEAR",
        sorted_clusters[1][0]: "SIDEWAYS",
        sorted_clusters[2][0]: "BULL",
    }

    # Current bar features
    current_features = feat_df[feature_cols].iloc[-1].values.reshape(1, -1)
    current_scaled   = scaler.transform(current_features)
    current_label    = int(kmeans.predict(current_scaled)[0])
    current_regime   = regime_map[current_label]

    # Confidence: inverse of within-cluster distance spread (normalised)
    distances = kmeans.transform(current_scaled)[0]  # dist to each centroid
    min_d, second_d = sorted(distances)[:2]
    # Higher separation = higher confidence
    separation = (second_d - min_d) / (second_d + 1e-9)
    confidence = float(np.clip(0.50 + separation * 0.45, 0.50, 0.95))

    # Recent cluster distribution (last 20 bars) for stability check
    recent_labels = labels[-20:]
    dominant_count = int(np.sum(recent_labels == current_label))
    stability_pct  = dominant_count / len(recent_labels)

    result = {
        "regime":      current_regime,
        "confidence":  round(confidence, 3),
        "stability":   round(stability_pct, 2),
        "params":      REGIME_PARAMS[current_regime],
        "cluster_returns": {regime_map[k]: round(v * 100, 4) for k, v in cluster_returns.items()},
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist for dashboard
    with open(REGIME_FILE, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        f"[REGIME] {current_regime} | conf={confidence:.2f} | stability={stability_pct:.0%} | cluster_returns={result['cluster_returns']}"
    )
    return result


def _fallback_regime(error_msg=""):
    """Return SIDEWAYS as safe fallback when detection fails."""
    result = {
        "regime":      "SIDEWAYS",
        "confidence":  0.5,
        "stability":   0.0,
        "params":      REGIME_PARAMS["SIDEWAYS"],
        "cluster_returns": {},
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "error":       error_msg,
    }
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        with open(REGIME_FILE, "w") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass
    return result


def get_regime_params(regime: str) -> dict:
    return REGIME_PARAMS.get(regime, REGIME_PARAMS["SIDEWAYS"])


if __name__ == "__main__":
    result = detect_regime()
    print(f"Current regime: {result['regime']} (confidence={result['confidence']:.2f}, stability={result['stability']:.0%})")
    print(f"Params: {result['params']}")
    print(f"Cluster returns: {result['cluster_returns']}")
