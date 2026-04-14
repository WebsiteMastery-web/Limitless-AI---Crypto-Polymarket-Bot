from flask import Flask, request, jsonify, send_file
import json, os, glob, math, random
from datetime import datetime, timezone
from loguru import logger
import json
import sys
from datetime import datetime


app = Flask(__name__)
LOG_DIR = "/root/limitless-ai/logs/mirofish"
SENDER = "/root/limitless-ai/mirofish_sender.py"
HEADLINE_CACHE = "/root/limitless-ai/logs/latest_headline.json"
RECEIVER_LOG = "/root/limitless-ai/logs/mirofish_receiver.log"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(RECEIVER_LOG), exist_ok=True)

# Configure loguru to also write to receiver log file
logger.add(RECEIVER_LOG, rotation="10 MB", retention="7 days", level="INFO")

# Keyword scoring for rule-based simulation
BULLISH_KEYWORDS = [
    "bullish",
    "rally",
    "surge",
    "soar",
    "rise",
    "pump",
    "accumulation",
    "buy",
    "institutional",
    "etf",
    "approval",
    "halving",
    "adoption",
    "record",
    "high",
    "breakout",
    "support",
    "hodl",
    "moon",
    "green",
    "positive",
    "growth",
    "recovery",
    "rebound",
    "gains",
    "profit",
]
BEARISH_KEYWORDS = [
    "bearish",
    "crash",
    "dump",
    "fall",
    "drop",
    "sell",
    "ban",
    "regulation",
    "fear",
    "panic",
    "hack",
    "scam",
    "fraud",
    "liquidation",
    "red",
    "negative",
    "loss",
    "decline",
    "collapse",
    "warning",
    "risk",
    "volatile",
    "uncertainty",
    "correction",
    "resistance",
    "overvalued",
    "bubble",
]

NUM_SIMULATE_AGENTS = 250


def score_headline(headline):
    """Score a headline with keyword matching. Returns float in [-1, 1]."""
    text = headline.lower()
    score = 0
    for kw in BULLISH_KEYWORDS:
        if kw in text:
            score += 1
    for kw in BEARISH_KEYWORDS:
        if kw in text:
            score -= 1
    # Normalize to [-1, 1] range
    max_possible = max(len(BULLISH_KEYWORDS), len(BEARISH_KEYWORDS))
    return max(-1.0, min(1.0, score / max(1, max_possible) * 5))


def simulate_agents_rule_based(headline, num_agents=NUM_SIMULATE_AGENTS):
    """Simulate agents using keyword scoring + gaussian noise."""
    base_score = score_headline(headline)
    results = []
    for _ in range(num_agents):
        # Add gaussian noise around the base score
        agent_score = base_score + random.gauss(0, 0.3)
        if agent_score > 0.15:
            results.append("BULLISH")
        elif agent_score < -0.15:
            results.append("BEARISH")
        else:
            results.append("NEUTRAL")
    return results


def get_minutes_since_last_signal():
    """Return minutes since the most recent mirofish log file was created."""
    files = sorted(glob.glob(f"{LOG_DIR}/*.json"), reverse=True)
    if not files:
        return None
    try:
        mtime = os.path.getmtime(files[0])
        last_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta_minutes = (now - last_dt).total_seconds() / 60
        return round(delta_minutes, 1)
    except:
        return None


def get_total_signals():
    """Count total mirofish signal files received."""
    return len(glob.glob(f"{LOG_DIR}/*.json"))


@app.route("/sender_script", methods=["GET"])
def sender_script():
    return send_file(SENDER, mimetype="text/plain", as_attachment=True)



def get_enriched_context():
    """Build context package for MiroFish sender to use in agent prompts."""
    from loguru import logger
    
    context = {
        "timestamp": datetime.utcnow().isoformat(),
        "btc_price": None,
        "price_change_24h_pct": None,
        "regime": "UNKNOWN",
        "regime_detail": "",
        "primary_headline": "",
        "supporting_headlines": [],
        "geopolitical_signal": "",
        "mirofish_goal": "BTC_SENTIMENT"
    }
    
    # 1. Get BTC price and 24h change from yfinance, with pipeline_runs fallback.
    # If yfinance fails, reads last two entries from pipeline_runs.jsonl.
    # If that also fails, defaults to 0.0 (neutral assumption) rather than null.
    try:
        import yfinance as yf
        btc = yf.Ticker("BTC-USD")
        hist = btc.history(period="2d", interval="1d")
        if len(hist) >= 2:
            current_price = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            context["btc_price"] = round(current_price, 0)
            context["price_change_24h_pct"] = round(change_pct, 2)
        elif len(hist) == 1:
            context["btc_price"] = round(hist["Close"].iloc[-1], 0)
    except Exception as e:
        logger.warning(f"yfinance BTC fetch failed: {e} -- trying pipeline_runs fallback")
        try:
            with open("/root/limitless-ai/logs/pipeline_runs.jsonl") as _f:
                _lines = [l for l in _f if l.strip()]
            if len(_lines) >= 2:
                _r1 = json.loads(_lines[-2])
                _r2 = json.loads(_lines[-1])
                _p1 = _r1.get("price_at_decision")
                _p2 = _r2.get("price_at_decision")
                if _p1 and _p2 and float(_p1) > 0:
                    context["price_change_24h_pct"] = round(((float(_p2) - float(_p1)) / float(_p1)) * 100, 2)
                    context["btc_price"] = round(float(_p2), 0)
                    logger.warning(f"BTC fallback via pipeline_runs: {_p1} -> {_p2}")
                else:
                    context["price_change_24h_pct"] = 0.0
                    logger.warning("No valid BTC prices in pipeline_runs, defaulting price_change_24h_pct=0.0")
            else:
                context["price_change_24h_pct"] = 0.0
                logger.warning("Insufficient pipeline_runs entries for BTC fallback, defaulting 0.0")
        except Exception as _e2:
            context["price_change_24h_pct"] = 0.0
            logger.warning(f"BTC pipeline fallback failed: {_e2} -- defaulting price_change_24h_pct=0.0")
    
    # 1b. If price_change_24h_pct still None (yfinance returned < 2 rows),
    # try pipeline_runs fallback, then default to 0.0.
    if context["price_change_24h_pct"] is None:
        try:
            with open("/root/limitless-ai/logs/pipeline_runs.jsonl") as _f:
                _lines = [l for l in _f if l.strip()]
            if len(_lines) >= 2:
                _r1 = json.loads(_lines[-2])
                _r2 = json.loads(_lines[-1])
                _p1 = _r1.get("price_at_decision")
                _p2 = _r2.get("price_at_decision")
                if _p1 and _p2 and float(_p1) > 0:
                    context["price_change_24h_pct"] = round(((float(_p2) - float(_p1)) / float(_p1)) * 100, 2)
                    if context["btc_price"] is None:
                        context["btc_price"] = round(float(_p2), 0)
                    logger.warning(f"price_change_24h_pct fallback: {_p1} -> {_p2}")
                else:
                    context["price_change_24h_pct"] = 0.0
                    logger.warning("price_change_24h_pct: no pipeline_runs prices, defaulting 0.0")
            else:
                context["price_change_24h_pct"] = 0.0
                logger.warning("price_change_24h_pct: insufficient pipeline_runs, defaulting 0.0")
        except Exception as _e3:
            context["price_change_24h_pct"] = 0.0
            logger.warning(f"price_change_24h_pct fallback failed: {_e3} -- defaulting 0.0")

    # 2. Get regime from latest pipeline run
    try:
        with open("/root/limitless-ai/logs/pipeline_runs.jsonl") as f:
            lines = [l for l in f if l.strip()]
        if lines:
            last_run = json.loads(lines[-1])
            reasoning = last_run.get("reasoning_summary", "")
            if "bull market" in reasoning.lower():
                context["regime"] = "BULL"
            elif "bear market" in reasoning.lower():
                context["regime"] = "BEAR"
            elif "sideways" in reasoning.lower() or "range" in reasoning.lower():
                context["regime"] = "SIDEWAYS"
            elif "volatile" in reasoning.lower():
                context["regime"] = "VOLATILE"
            decision = last_run.get("decision", "")
            if decision in ["BUY", "SELL", "HOLD"]:
                context["regime_detail"] = decision
    except Exception as e:
        logger.warning(f"Failed to get regime: {e}")
    
    # 3. Get headlines from latest_headline.json cache (Tavily-fetched news), or pipeline_runs.jsonl.
    # IMPORTANT: NEVER read from trade_journal.jsonl "reasoning", "decision", "rationale", or any
    # Portfolio Manager output field. Those contain the system's own trading decisions, NOT news.
    # MiroFish agents must receive real external news articles, not their own system's outputs.
    _HEADLINE_CACHE_MAX_AGE = 2 * 3600  # 2 hours in seconds
    try:
        _cache_used = False
        if os.path.exists(HEADLINE_CACHE):
            from datetime import timezone as _tz
            _cache_age = (datetime.now(tz=_tz.utc) - datetime.fromtimestamp(
                os.path.getmtime(HEADLINE_CACHE), tz=_tz.utc)).total_seconds()
            if _cache_age < _HEADLINE_CACHE_MAX_AGE:
                with open(HEADLINE_CACHE) as f:
                    _hdata = json.load(f)
                _hl = _hdata.get("headline", "")
                if _hl:
                    context["primary_headline"] = _hl
                    _cache_used = True
                    logger.debug("Headlines: using latest_headline.json cache")
        if not _cache_used:
            # Fallback: pipeline_runs.jsonl — look for actual news content fields only
            try:
                with open("/root/limitless-ai/logs/pipeline_runs.jsonl") as f:
                    _pr_lines = [l for l in f if l.strip()]
                if _pr_lines:
                    _last_pr = json.loads(_pr_lines[-1])
                    # Only read actual news fields — never reasoning_summary or portfolio decisions
                    _news = (_last_pr.get("news_summary") or
                             _last_pr.get("tavily_headlines") or
                             _last_pr.get("tavily_articles") or "")
                    if _news and isinstance(_news, str):
                        context["primary_headline"] = _news[:300]
                    elif _news and isinstance(_news, list):
                        context["primary_headline"] = str(_news[0])[:300] if _news else ""
                        context["supporting_headlines"] = [str(h)[:200] for h in _news[1:3]]
                    else:
                        logger.warning("Headlines: no news fields in pipeline_runs, leaving empty")
            except Exception as _e2:
                logger.warning(f"Headlines pipeline_runs fallback failed: {_e2}")
        # Tavily live fetch when both cache and pipeline fallback failed
        if not context["primary_headline"]:
            try:
                _env_path = "/root/limitless-ai/TradingAgents/.env"
                _tavily_key = None
                if os.path.exists(_env_path):
                    with open(_env_path) as _ef:
                        for _line in _ef:
                            if _line.strip().startswith("TAVILY_API_KEY="):
                                _tavily_key = _line.strip().split("=", 1)[1].strip().strip("'").strip('"')
                                break
                if _tavily_key:
                    import requests as _req
                    _tr = _req.post("https://api.tavily.com/search", json={
                        "api_key": _tavily_key,
                        "query": "Bitcoin BTC crypto market news today",
                        "search_depth": "basic",
                        "max_results": 5
                    }, timeout=10)
                    if _tr.status_code == 200:
                        _t_results = _tr.json().get("results", [])
                        if _t_results:
                            _t0 = _t_results[0]
                            _hl = (_t0.get("title", "") + " -- " + _t0.get("content", "")[:150]).strip(" --")
                            context["primary_headline"] = _hl[:300]
                            context["supporting_headlines"] = [
                                (r.get("title", "") + " -- " + r.get("content", "")[:100]).strip(" --")[:200]
                                for r in _t_results[1:4]
                            ]
                            with open(HEADLINE_CACHE, 'w') as _hf:
                                json.dump({'headline': context['primary_headline'], 'fetched_at': datetime.now(timezone.utc).isoformat()}, _hf)
                            logger.info('Headlines: Tavily live fetch OK: ' + context['primary_headline'][:80])
                        else:
                            logger.warning('Headlines: Tavily returned 0 results')
                    else:
                        logger.warning('Headlines: Tavily API error ' + str(_tr.status_code))
                else:
                    logger.warning('Headlines: TAVILY_API_KEY not found in .env')
            except Exception as _te:
                logger.warning('Headlines: Tavily live fetch failed: ' + str(_te))
    except Exception as e:
        logger.warning(f"Failed to get headlines: {e}")
    
    # 4. Get geopolitical signal from dedicated pipeline_run fields only.
    # IMPORTANT: NEVER parse "reasoning_summary" or any Portfolio Manager output for geo signals.
    # Those fields contain trading decisions, not real geopolitical classifications.
    # If no dedicated geo field exists in pipeline_runs, geopolitical_signal stays empty.
    try:
        with open("/root/limitless-ai/logs/pipeline_runs.jsonl") as f:
            lines = [l for l in f if l.strip()]
        if lines:
            last_run = json.loads(lines[-1])
            geo_signal = (last_run.get("geopolitical_result") or
                          last_run.get("geo_signal") or
                          last_run.get("geopolitical_signal") or "")
            context["geopolitical_signal"] = str(geo_signal)[:200] if geo_signal else ""
    except Exception as e:
        logger.warning(f"Failed to get geopolitical signal: {e}")
    
    return context


@app.route("/latest_headlines", methods=["GET"])
def latest_headlines():
    """Return enriched context package for MiroFish sender."""
    context = get_enriched_context()
    return jsonify(context)
@app.route("/mirofish", methods=["POST"])
def receive():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no data"}), 400
    data["received_at"] = datetime.utcnow().isoformat()
    ts = data.get("timestamp", datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    path = f"{LOG_DIR}/mirofish_{ts}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log_msg = f"MiroFish RECEIVED: label={data.get('sentiment_label')} score={data.get('sentiment_score')} agents={data.get('agent_count')} ts={ts}"
    logger.info(log_msg)
    return jsonify({"status": "ok"}), 200


@app.route("/mirofish/latest", methods=["GET"])
def latest():
    files = sorted(glob.glob(f"{LOG_DIR}/*.json"), reverse=True)
    if not files:
        return jsonify({"status": "no_data"}), 404
    with open(files[0]) as f:
        return jsonify(json.load(f)), 200


@app.route("/health", methods=["GET"])
def health():
    minutes_ago = get_minutes_since_last_signal()
    total_signals = get_total_signals()
    return jsonify(
        {
            "status": "ok",
            "last_signal_minutes_ago": minutes_ago,
            "total_signals_received": total_signals,
        }
    ), 200


@app.route("/simulate", methods=["GET"])
def simulate():
    """
    VPS fallback simulation — runs when the PC/sender is offline.
    Uses rule-based keyword scoring with gaussian noise across 250 simulated agents.
    Fast path only — no Ollama calls to keep response time under 1 second.
    """
    start_time = datetime.utcnow()

    # Load latest headline
    headline = "Bitcoin BTC price analysis crypto market outlook today"
    headline_source = "default"
    try:
        if os.path.exists(HEADLINE_CACHE):
            with open(HEADLINE_CACHE) as f:
                data = json.load(f)
            if data.get("headline"):
                headline = data["headline"]
                headline_source = "cache"
    except:
        pass

    # Rule-based simulation — instant, no external dependencies
    model_used = "rule-based-gaussian"
    results = simulate_agents_rule_based(headline, NUM_SIMULATE_AGENTS)

    counts = {lbl: results.count(lbl) for lbl in ["BULLISH", "BEARISH", "NEUTRAL"]}
    total = len(results)
    score = round((counts["BULLISH"] - counts["BEARISH"]) / total, 3)
    label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")
    ts = start_time.strftime("%Y%m%d_%H%M%S")
    duration = round((datetime.utcnow() - start_time).total_seconds(), 3)

    payload = {
        "sentiment_score": score,
        "sentiment_label": label,
        "agent_count": NUM_SIMULATE_AGENTS,
        "model_used": model_used,
        "duration_seconds": duration,
        "news_article": headline,
        "headline_source": headline_source,
        "counts": counts,
        "timestamp": ts,
        "source": "vps_simulate_endpoint",
        "received_at": start_time.isoformat(),
    }

    # Save to logs
    path = f"{LOG_DIR}/mirofish_{ts}.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(
        f"Simulate: label={label} score={score} model={model_used} duration={duration}s"
    )
    return jsonify(payload), 200




@app.route('/polymarket_questions', methods=['GET'])
def polymarket_questions():
    try:
        positions_path = '/root/limitless-ai/logs/polymarket_positions.json'
        with open(positions_path) as f:
            positions = json.load(f)
        
        # Filter open positions
        open_positions = [p for p in positions if p.get('status') == 'open']
        
        # Sort by edge descending — highest edge questions first
        open_positions.sort(key=lambda x: x.get('edge', 0), reverse=True)
        
        # Return top 5
        result = []
        for p in open_positions[:5]:
            result.append({
                'market_id': p.get('market_id', ''),
                'question': p.get('market_question', ''),
                'market_yes_price': p.get('market_yes_price') or p.get('yes_price_at_entry') or p.get('entry_prob') or p.get('entry_probability', 0.5),
                'edge': p.get('edge', 0),
                'system_side': p.get('side', ''),
                'key_reason': p.get('key_reason', '')
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify([])


@app.route('/polymarket_mirofish', methods=['POST'])
def receive_polymarket_mirofish():
    try:
        data = request.get_json()
        if not data or 'results' not in data:
            return jsonify({'status': 'error', 'message': 'Missing results key'}), 400
        
        results = data['results']
        
        # Save to timestamped file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = f'/root/limitless-ai/logs/mirofish/polymarket_mirofish_{timestamp}.json'
        
        with open(save_path, 'w') as f:
            json.dump({
                'received_at': datetime.utcnow().isoformat(),
                'results': results,
                'result_count': len(results)
            }, f, indent=2)
        
        print(f'[{timestamp}] Received MiroFish Polymarket assessment: {len(results)} markets')
        return jsonify({'status': 'ok', 'saved': len(results), 'path': save_path})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
if __name__ == "__main__":
    logger.info("MiroFish receiver starting on port 9876")
    app.run(host="0.0.0.0", port=9876, debug=False)
