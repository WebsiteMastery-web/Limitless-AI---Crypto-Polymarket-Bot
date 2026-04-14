import os, requests, json
from datetime import datetime

VOLATILITY_KW = ["tariff", "sanction", "reversal", "escalation", "emergency",
                  "executive order", "pivot", "threat", "ceasefire", "ban"]

TAVILY = "https://api.tavily.com/search"

def get_policy_signal() -> dict:
    """
    Layer 12: Macro/political policy event detector.
    HIGH_VOLATILITY → raise PM confidence threshold to 70%.
    Cost: ~$0.0003/run (Tavily, already in budget).
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"regime": "NORMAL", "conf": 0.5, "events": 0, "threshold": "65%"}

    try:
        r = requests.post(TAVILY, json={
            "api_key": api_key,
            "query": "Trump policy announcement market impact tariff sanction",
            "search_depth": "basic",
            "max_results": 5,
            "days": 2,
            "include_answer": False,
            "include_raw_content": False
        }, timeout=10)

        if r.status_code != 200:
            return {"regime": "NORMAL", "conf": 0.5, "events": 0,
                    "threshold": "65%", "err": f"tavily:{r.status_code}"}

        results = r.json().get("results", [])
        hits = sum(
            1 for item in results
            if sum(1 for kw in VOLATILITY_KW
                   if kw in (item.get("title","") + item.get("content","")[:150]).lower()) >= 2
        )

        if hits >= 3:
            regime, conf, thresh = "HIGH_VOLATILITY", 0.80, "70%"
        elif hits >= 1:
            regime, conf, thresh = "ELEVATED", 0.60, "65%"
        else:
            regime, conf, thresh = "NORMAL", 0.70, "65%"

        return {"regime": regime, "conf": conf, "events": hits,
                "threshold": thresh, "ts": datetime.utcnow().isoformat()}

    except Exception as e:
        return {"regime": "NORMAL", "conf": 0.5, "events": 0,
                "threshold": "65%", "err": str(e)[:60]}

def fmt_policy(r: dict) -> str:
    return f"[L12:Policy] {r['regime']} | events:{r['events']} | PM_threshold:{r['threshold']}"

if __name__ == "__main__":
    r = get_policy_signal()
    print(json.dumps(r, indent=2))
    print(f"\nPipeline ({len(fmt_policy(r))} chars): {fmt_policy(r)}")
