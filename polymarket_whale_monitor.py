import requests, json
from datetime import datetime

GAMMA = "https://gamma-api.polymarket.com"

def get_whale_signal(min_vol: float = 50000, limit: int = 20) -> dict:
    """
    Layer 11: Polymarket whale positioning (LOW RELIABILITY — 50% weight).
    Detects where large capital is positioned via market price extremes.
    Cost: $0. Uses existing Gamma API (no auth required).
    """
    try:
        r = requests.get(f"{GAMMA}/markets", params={
            "limit": limit, "active": "true",
            "order": "volume24hr", "ascending": "false"
        }, timeout=8)
        if r.status_code != 200:
            return {"signal": "NEUTRAL", "conf": 0.3, "err": f"api:{r.status_code}"}
        
        markets = r.json()
        yes_dom, no_dom = 0, 0
        
        for m in markets:
            try:
                prices_raw = m.get("outcomePrices") or "[]"
                prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                if not prices:
                    continue
                yes_p = float(prices[0])
                vol = float(m.get("volume24hr") or m.get("volume") or 0)
                if vol < min_vol:
                    continue
                if yes_p > 0.72:
                    yes_dom += 1
                elif yes_p < 0.28:
                    no_dom += 1
            except:
                continue
        
        total = yes_dom + no_dom
        if total == 0:
            return {"signal": "NEUTRAL", "conf": 0.3, "yes_dom": 0, "no_dom": 0}
        
        ratio = yes_dom / total
        if ratio >= 0.65:
            sig, conf = "BULLISH", min(ratio, 0.70)
        elif ratio <= 0.35:
            sig, conf = "BEARISH", min(1 - ratio, 0.70)
        else:
            sig, conf = "NEUTRAL", 0.40
        
        return {"signal": sig, "conf": round(conf, 3),
                "yes_dom": yes_dom, "no_dom": no_dom,
                "ts": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"signal": "NEUTRAL", "conf": 0.3, "err": str(e)[:60]}

def fmt_whale(r: dict) -> str:
    """Compact format. PM must weight this at 50% of other layers."""
    if r.get("err"):
        return f"[L11:Whale-LOW] UNAVAIL | {r['err'][:40]}"
    return f"[L11:Whale-LOW] {r['signal']} {r['conf']:.0%} | YES-dom:{r.get('yes_dom',0)} NO-dom:{r.get('no_dom',0)} | LOW_RELIABILITY"

if __name__ == "__main__":
    r = get_whale_signal()
    print(json.dumps(r, indent=2))
    print(f"\nPipeline ({len(fmt_whale(r))} chars): {fmt_whale(r)}")
