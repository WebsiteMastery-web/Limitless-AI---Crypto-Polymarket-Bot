from flask import Flask, request, jsonify, send_file
import json, os, glob
from datetime import datetime
from loguru import logger

app = Flask(__name__)
LOG_DIR = "/root/limitless-ai/logs/mirofish"
SENDER = "/root/limitless-ai/mirofish_sender.py"
HEADLINE_CACHE = "/root/limitless-ai/logs/latest_headline.json"
os.makedirs(LOG_DIR, exist_ok=True)

@app.route("/sender_script", methods=["GET"])
def sender_script():
    return send_file(SENDER, mimetype="text/plain", as_attachment=True)

@app.route("/latest_headlines", methods=["GET"])
def latest_headlines():
    """Return latest BTC headline from Tavily for MiroFish to use."""
    try:
        if os.path.exists(HEADLINE_CACHE):
            with open(HEADLINE_CACHE) as f:
                data = json.load(f)
            if data.get("headline"):
                return jsonify(data), 200
    except:
        pass
    # Live fetch as fallback
    try:
        import sys
        sys.path.insert(0, "/root/limitless-ai/TradingAgents")
        from dotenv import load_dotenv
        load_dotenv("/root/limitless-ai/TradingAgents/.env")
        from tavily import TavilyClient
        import os as _os
        client = TavilyClient(api_key=_os.getenv("TAVILY_API_KEY"))
        results = client.search(query="Bitcoin BTC price news today", max_results=1, include_answer=True)
        headline = results.get("answer", "") or (results.get("results", [{}])[0].get("title", ""))
        if headline:
            data = {"headline": headline[:200], "fetched_at": datetime.utcnow().isoformat()}
            with open(HEADLINE_CACHE, "w") as f:
                json.dump(data, f)
            return jsonify(data), 200
    except Exception as e:
        logger.warning(f"Headline fetch failed: {e}")
    return jsonify({"headline": "Bitcoin BTC price analysis crypto market outlook today"}), 200

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
    logger.info(f"MiroFish: {data.get('sentiment_label')} score={data.get('sentiment_score')} agents={data.get('agent_count')}")
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
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    logger.info("MiroFish receiver on port 9876")
    app.run(host="0.0.0.0", port=9876, debug=False)
