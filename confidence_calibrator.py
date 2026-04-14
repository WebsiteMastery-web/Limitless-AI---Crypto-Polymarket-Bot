#!/usr/bin/env python3
"""
Limitless AI - Isotonic Confidence Calibrator
Builds a calibration model mapping raw PM confidence -> true win probability.
Run weekly via cron. Requires 10+ resolved BUY/SELL signals to fit.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression

LOGS_DIR = Path("/root/limitless-ai/logs")
BACKTEST_FILE = LOGS_DIR / "backtest_results.jsonl"
JOURNAL_FILE  = LOGS_DIR / "trade_journal.jsonl"
CALIB_DATA    = LOGS_DIR / "calibration_data.json"
CALIB_MODEL   = LOGS_DIR / "calibration_model.json"

MIN_SAMPLES = 10
RETRAIN_THRESHOLD = 20


def load_records():
    dataset = []

    for filepath, source in [(BACKTEST_FILE, "backtest"), (JOURNAL_FILE, "journal")]:
        if not filepath.exists():
            continue
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                decision = r.get("decision", "").upper()
                outcome  = r.get("outcome", "").upper()
                conf     = r.get("confidence")
                if decision in ("BUY", "SELL") and outcome in ("WIN", "LOSS") and conf is not None:
                    dataset.append({
                        "raw_confidence": int(conf),
                        "outcome_binary": 1 if outcome == "WIN" else 0,
                        "source": source,
                    })

    return dataset


def main():
    print("[CALIBRATOR] Loading resolved BUY/SELL signals from backtest + journal...")
    dataset = load_records()
    print(f"[CALIBRATOR] Found {len(dataset)} qualifying records.")

    with open(CALIB_DATA, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"[CALIBRATOR] Saved dataset -> {CALIB_DATA}")

    if len(dataset) < MIN_SAMPLES:
        print(f"WARNING: Need at least {MIN_SAMPLES} resolved signals for calibration.")
        print(f"         Currently have {len(dataset)}. Check back when more trades resolve.")
        print("         Calibration model NOT updated.")
        sys.exit(0)

    X = np.array([r["raw_confidence"] for r in dataset])
    y = np.array([r["outcome_binary"]  for r in dataset])

    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(X, y)

    calibration_curve = []
    for conf in range(50, 100, 5):
        calibrated = float(ir.predict([conf])[0])
        calibration_curve.append({
            "raw_confidence": conf,
            "calibrated_probability": round(calibrated, 3),
        })

    win_rate = float(np.mean(y))

    model = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_samples": len(X),
        "win_rate_raw": round(win_rate, 3),
        "calibration_curve": calibration_curve,
        "note": f"Retrain when new_samples > {len(X) + RETRAIN_THRESHOLD}",
    }

    with open(CALIB_MODEL, "w") as f:
        json.dump(model, f, indent=2)
    print(f"[CALIBRATOR] Model saved -> {CALIB_MODEL}")
    print(f"[CALIBRATOR] Training samples: {len(X)} | Win rate: {win_rate:.1%}")
    print("[CALIBRATOR] Calibration curve:")
    for pt in calibration_curve:
        bar = "#" * int(pt["calibrated_probability"] * 20)
        print(f"  raw={pt['raw_confidence']:3d}%  -> calibrated={pt['calibrated_probability']:.3f}  {bar}")

    probs = [pt["calibrated_probability"] for pt in calibration_curve]
    is_monotone = all(probs[i] <= probs[i+1] for i in range(len(probs)-1))
    if not is_monotone:
        print("WARNING: Calibration curve is not monotonically increasing.")
    else:
        print("[CALIBRATOR] OK: curve is monotonically non-decreasing.")

    if len(set(probs)) == 1:
        print("WARNING: All confidences map to same probability - dataset too small/homogeneous.")
        print("         Check again in 4 weeks when more trades have resolved.")


if __name__ == "__main__":
    main()
