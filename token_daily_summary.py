import json, os
from datetime import datetime, timedelta

LOG = "/root/limitless-ai/logs/token_costs.jsonl"

def daily_summary():
    if not os.path.exists(LOG):
        print("No token log yet."); return
    today = datetime.utcnow().date()
    today_cost = month_cost = today_calls = 0
    with open(LOG) as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                ts = datetime.fromisoformat(e["ts"]).date()
                c = float(e.get("cost_usd", 0))
                if ts == today: today_cost += c; today_calls += 1
                if ts.month == today.month and ts.year == today.year: month_cost += c
            except: continue
    proj = month_cost * 30 / max(today.day, 1)
    print(f"TODAY ({today}): ${today_cost:.4f} ({today_calls} PM calls)")
    print(f"MONTH: ${month_cost:.4f} | PROJECTED: ${proj:.2f}")

if __name__ == "__main__":
    daily_summary()
