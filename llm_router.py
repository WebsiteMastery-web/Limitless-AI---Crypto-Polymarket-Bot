import os, time, requests, json

ANTHROPIC_BASE = "https://api.anthropic.com/v1/messages"

SIMPLE_MODEL = "claude-sonnet-4-6"
PM_MODEL = "claude-opus-4-6"

def _headers():
    return {
        "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

def call_simple(system_prompt: str, user_content: str, max_tokens: int = 400) -> dict:
    try:
        system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
        messages = [{"role": "user", "content": user_content}]
        t0 = time.time()
        r = requests.post(ANTHROPIC_BASE, headers=_headers(),
            json={"model": SIMPLE_MODEL, "system": system, "messages": messages, "max_tokens": max_tokens},
            timeout=45)
        ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            print(f"[Router:simple] {SIMPLE_MODEL}: {r.status_code}, failed. {r.text[:200]}")
            return {"content": "", "model": "FAILED", "ms": ms, "usage": {}}
        data = r.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        print(f"[Router:simple] {SIMPLE_MODEL} | {ms}ms | in:{usage.get('input_tokens',0)} out:{usage.get('output_tokens',0)}")
        return {"content": content, "model": SIMPLE_MODEL, "ms": ms, "usage": usage}
    except Exception as e:
        print(f"[Router:simple] Exception: {e}")
        return {"content": "", "model": "FAILED", "ms": 0, "usage": {}}

def call_pm(static_protocol: str, static_kb: str, dynamic_signals: str, max_tokens: int = 600) -> dict:
    system = [{"type": "text", "text": static_protocol, "cache_control": {"type": "ephemeral"}}]
    if static_kb:
        system.append({"type": "text", "text": static_kb, "cache_control": {"type": "ephemeral"}})
    messages = [{"role": "user", "content": dynamic_signals}]
    try:
        t0 = time.time()
        r = requests.post(ANTHROPIC_BASE, headers=_headers(),
            json={"model": PM_MODEL, "system": system, "messages": messages, "max_tokens": max_tokens},
            timeout=90)
        ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            print(f"[Router:PM] Opus error {r.status_code}: {r.text[:200]}")
            return {"content": "DECISION: HOLD\nCONFIDENCE: 0\nPRIMARY_DRIVER: LLM_FAIL\nREASONING: Opus unavailable.",
                    "model": "FALLBACK_HOLD", "ms": 0, "usage": {}}
        data = r.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        cache_hit = usage.get("cache_read_input_tokens", 0)
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        cost = (cache_hit * 0.75 + (in_tok - cache_hit) * 15.0) / 1_000_000 + (out_tok * 75.0) / 1_000_000
        print(f"[Router:PM] {PM_MODEL} | {ms}ms | in:{in_tok} cached:{cache_hit} out:{out_tok} | est:${cost:.5f}")
        return {"content": content, "model": PM_MODEL, "ms": ms, "usage": usage, "cost_usd": cost}
    except Exception as e:
        print(f"[Router:PM] Exception: {e}")
        return {"content": "DECISION: HOLD\nCONFIDENCE: 0\nPRIMARY_DRIVER: LLM_EXCEPTION\nREASONING: Exception in PM call.",
                "model": "FALLBACK_HOLD", "ms": 0, "usage": {}}

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("/root/limitless-ai/TradingAgents/.env")
    print("Testing simple route (Sonnet 4.6)...")
    r = call_simple("You are a test agent.", "Say HELLO in 3 words max.", 20)
    print(f"Simple: {r['content'][:50]} | model: {r['model']}")
    print("\nTesting PM route (Opus 4.6)...")
    r = call_pm("You are a PM.", "KB: BTC bull market.", "Signal: BULLISH from EDGAR. BTC +2%.", 100)
    print(f"PM: {r['content'][:80]} | model: {r['model']} | cost: ${r.get('cost_usd',0):.5f}")
